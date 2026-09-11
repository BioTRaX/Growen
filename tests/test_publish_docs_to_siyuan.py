#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_publish_docs_to_siyuan.py
# NG-HEADER: Ubicación: tests/test_publish_docs_to_siyuan.py
# NG-HEADER: Descripción: Pruebas de sincronización segura de Markdown Git hacia SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts import publish_docs_to_siyuan as publisher


class FakeService:
    def __init__(self, documents: dict[str, str] | None = None) -> None:
        self.documents: dict[str, dict[str, str]] = {}
        for index, (path, markdown) in enumerate((documents or {}).items(), start=1):
            self.documents[path] = {
                "document_id": f"2026082712345{index}-abcdefg",
                "markdown": markdown,
                "revision_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            }
        self.created: list[tuple[str, str]] = []
        self.updated: list[tuple[str, str, str]] = []
        self.deleted: list[tuple[str, str]] = []

    async def find_document_by_path(self, path: str):
        document = self.documents.get(path)
        return document["document_id"] if document else None

    async def read_document(self, document_id: str):
        path, document = next(
            (path, document)
            for path, document in self.documents.items()
            if document["document_id"] == document_id
        )
        return {
            "document_id": document_id,
            "hpath": path,
            "markdown": document["markdown"],
            "revision_sha256": document["revision_sha256"],
        }

    async def create_git_document(self, path: str, markdown: str):
        self.created.append((path, markdown))
        document_id = f"2026082712345{5 + len(self.created)}-abcdefg"
        self.documents[path] = {
            "document_id": document_id,
            "markdown": markdown,
            "revision_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
        }
        return {"document_id": document_id, "hpath": path, "created": True}

    async def update_git_document(
        self,
        document_id: str,
        markdown: str,
        expected_revision_sha256: str,
    ):
        path, document = next(
            (path, document)
            for path, document in self.documents.items()
            if document["document_id"] == document_id
        )
        assert document["revision_sha256"] == expected_revision_sha256
        self.updated.append((document_id, markdown, expected_revision_sha256))
        revision = hashlib.sha256(markdown.encode()).hexdigest()
        document.update(markdown=markdown, revision_sha256=revision)
        return {
            "document_id": document_id,
            "hpath": path,
            "updated": True,
            "previous_revision_sha256": expected_revision_sha256,
            "revision_sha256": revision,
        }

    async def remove_git_document_tree(self, path: str, expected_document_id: str):
        assert self.documents[path]["document_id"] == expected_document_id
        self.deleted.append((path, expected_document_id))
        for existing_path in list(self.documents):
            if existing_path == path or existing_path.startswith(f"{path}/"):
                del self.documents[existing_path]
        return {"deleted": True, "document_id": expected_document_id, "hpath": path}


class FailingCreateService(FakeService):
    def __init__(self, failing_path: str, documents: dict[str, str] | None = None) -> None:
        super().__init__(documents)
        self.failing_path = failing_path
        self.failed = False

    async def create_git_document(self, path: str, markdown: str):
        if path == self.failing_path and not self.failed:
            self.failed = True
            raise RuntimeError("fallo externo")
        return await super().create_git_document(path, markdown)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_all(root: Path) -> None:
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Growen Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "test fixture")


def test_siyuan_path_preserves_repository_structure() -> None:
    root = Path("C:/repo")

    assert publisher.siyuan_path(root / "README.md", root) == "/Growen/Documentación técnica/README"
    assert publisher.siyuan_path(root / "docs" / "MCP.md", root) == "/Growen/Documentación técnica/docs/MCP"


def test_discover_documents_includes_all_tracked_markdown_under_docs(tmp_path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("root", encoding="utf-8")
    (tmp_path / "OTHER.md").write_text("outside", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MCP.md").write_text("mcp", encoding="utf-8")
    (tmp_path / "docs" / "archive").mkdir()
    (tmp_path / "docs" / "archive" / "OLD.md").write_text("old", encoding="utf-8")
    (tmp_path / "docs" / "superpowers").mkdir()
    (tmp_path / "docs" / "superpowers" / "PLAN.md").write_text("plan", encoding="utf-8")
    (tmp_path / "docs" / "DRAFT.md").write_text("untracked", encoding="utf-8")
    _git(tmp_path, "add", "README.md", "OTHER.md", "docs/MCP.md", "docs/archive/OLD.md", "docs/superpowers/PLAN.md")

    documents = publisher.discover_documents(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in documents] == [
        "README.md",
        "docs/MCP.md",
        "docs/archive/OLD.md",
        "docs/superpowers/PLAN.md",
    ]


def test_assert_governed_documents_clean_rejects_modified_markdown(tmp_path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("estable", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    document = tmp_path / "docs" / "MCP.md"
    document.write_text("estable", encoding="utf-8")
    _commit_all(tmp_path)
    document.write_text("sin confirmar", encoding="utf-8")

    with pytest.raises(publisher.GitDocumentsDirtyError, match="git_documents_dirty"):
        publisher.assert_governed_documents_clean(tmp_path)


@pytest.mark.asyncio
async def test_rebuild_dry_run_plans_delete_and_recreate_without_writing(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("# Nueva", encoding="utf-8")
    root_path = "/Growen/Documentación técnica"
    service = FakeService({root_path: "# Anterior"})
    state = {"version": 1, "documents": {"docs/OLD.md": {"path": f"{root_path}/docs/OLD"}}}

    manifest, new_state = await publisher.rebuild_documents(
        [document],
        tmp_path,
        service,
        apply=False,
        confirmation=None,
        git_commit="a" * 40,
        state=state,
    )

    assert [entry["status"] for entry in manifest] == ["planned_delete", "planned_create"]
    assert service.deleted == []
    assert service.created == []
    assert new_state == state


@pytest.mark.asyncio
async def test_rebuild_apply_deletes_exact_root_and_checkpoints_complete_state(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("# Nueva", encoding="utf-8")
    root_path = "/Growen/Documentación técnica"
    service = FakeService({root_path: "# Anterior", f"{root_path}/docs/OLD": "viejo"})
    root_id = service.documents[root_path]["document_id"]
    checkpoints: list[dict] = []

    manifest, state = await publisher.rebuild_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        confirmation=root_path,
        git_commit="b" * 40,
        state={"version": 1, "documents": {"docs/OLD.md": {"path": f"{root_path}/docs/OLD"}}},
        checkpoint=lambda value: checkpoints.append(json.loads(json.dumps(value))),
    )

    assert service.deleted == [(root_path, root_id)]
    assert [entry["status"] for entry in manifest] == ["deleted", "created"]
    assert state["last_publish_commit"] == "b" * 40
    assert state["rebuild"]["phase"] == "complete"
    assert state["rebuild"]["deleted_document_id"] == root_id
    assert list(state["documents"]) == ["README.md"]
    assert any(checkpoint.get("rebuild", {}).get("phase") == "recreating" for checkpoint in checkpoints)


@pytest.mark.asyncio
async def test_rebuild_apply_rejects_wrong_confirmation_without_deleting(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("# Nueva", encoding="utf-8")
    root_path = "/Growen/Documentación técnica"
    service = FakeService({root_path: "# Anterior"})

    with pytest.raises(ValueError, match="rebuild_confirmation_invalid"):
        await publisher.rebuild_documents(
            [document],
            tmp_path,
            service,
            apply=True,
            confirmation="/Growen",
            git_commit="c" * 40,
            state={"version": 1, "documents": {}},
        )

    assert service.deleted == []


def test_document_secret_gate_rejects_known_token_shape_without_exposing_value(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("sk-" + "proj-" + "a" * 24, encoding="utf-8")

    with pytest.raises(publisher.DocumentationSecretError, match="documentation_secret_detected") as error:
        publisher.assert_no_document_secrets([document])

    assert "sk-" not in str(error.value)


@pytest.mark.asyncio
async def test_partial_rebuild_can_resume_without_deleting_again(tmp_path) -> None:
    first = tmp_path / "README.md"
    first.write_text("# Uno", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    second = docs / "MCP.md"
    second.write_text("# Dos", encoding="utf-8")
    root_path = "/Growen/Documentación técnica"
    failing_path = f"{root_path}/docs/MCP"
    service = FailingCreateService(failing_path, {root_path: "# Anterior"})

    first_manifest, partial_state = await publisher.rebuild_documents(
        [first, second],
        tmp_path,
        service,
        apply=True,
        confirmation=root_path,
        git_commit="d" * 40,
        state={"version": 1, "documents": {}},
    )

    assert any(entry["status"] == "error" for entry in first_manifest)
    assert partial_state["rebuild"]["phase"] == "recreating"
    assert len(service.deleted) == 1

    resumed_manifest, resumed_state = await publisher.publish_documents(
        [first, second],
        tmp_path,
        service,
        apply=True,
        state=partial_state,
    )
    resumed_state = publisher.finalize_rebuild_after_resume(
        resumed_state,
        resumed_manifest,
        [first, second],
        tmp_path,
        git_commit="d" * 40,
    )

    assert {entry["status"] for entry in resumed_manifest} == {"unchanged", "created"}
    assert resumed_state["rebuild"]["phase"] == "complete"
    assert len(service.deleted) == 1


@pytest.mark.asyncio
async def test_publish_manifest_contains_hash_but_not_content(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("contenido secreto de documentación", encoding="utf-8")
    path = publisher.siyuan_path(document, tmp_path)
    service = FakeService({path: "contenido divergente"})

    manifest, _ = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        state={"version": 1, "documents": {}},
    )

    assert manifest[0]["status"] == "conflict"
    assert manifest[0]["source_sha256"]
    assert "markdown" not in manifest[0]
    assert "contenido" not in str(manifest[0])


@pytest.mark.asyncio
async def test_dry_run_does_not_create_documents(tmp_path) -> None:
    document = tmp_path / "Nueva.md"
    document.write_text("# Nueva", encoding="utf-8")
    service = FakeService()

    manifest, state = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=False,
        state={"version": 1, "documents": {}},
    )

    assert manifest[0]["status"] == "planned_create"
    assert service.created == []
    assert state == {"version": 1, "documents": {}}


@pytest.mark.asyncio
async def test_apply_creates_document_and_records_post_write_revision(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("# Nueva", encoding="utf-8")
    service = FakeService()

    manifest, state = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        state={"version": 1, "documents": {}},
    )

    assert manifest[0]["status"] == "created"
    assert service.created == [("/Growen/Documentación técnica/README", "# Nueva")]
    saved = state["documents"]["README.md"]
    assert saved["document_id"] == "20260827123456-abcdefg"
    assert saved["source_sha256"] == hashlib.sha256(b"# Nueva").hexdigest()
    assert saved["siyuan_revision_sha256"] == hashlib.sha256(b"# Nueva").hexdigest()


@pytest.mark.asyncio
async def test_apply_checkpoints_state_after_each_confirmed_write(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("# Nueva", encoding="utf-8")
    checkpoints: list[dict] = []

    await publisher.publish_documents(
        [document],
        tmp_path,
        FakeService(),
        apply=True,
        state={"version": 1, "documents": {}},
        checkpoint=lambda state: checkpoints.append(
            json.loads(json.dumps(state))
        ),
    )

    assert len(checkpoints) == 1
    assert checkpoints[0]["documents"]["README.md"]["document_id"]


@pytest.mark.asyncio
async def test_apply_updates_when_only_git_changed_since_baseline(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("versión Git nueva", encoding="utf-8")
    path = publisher.siyuan_path(document, tmp_path)
    service = FakeService({path: "baseline"})
    document_id = service.documents[path]["document_id"]
    baseline_revision = hashlib.sha256(b"baseline").hexdigest()
    state = {
        "version": 1,
        "documents": {
            "README.md": {
                "path": path,
                "document_id": document_id,
                "source_sha256": hashlib.sha256(b"Git anterior").hexdigest(),
                "siyuan_revision_sha256": baseline_revision,
            }
        },
    }

    manifest, new_state = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        state=state,
    )

    assert manifest[0]["status"] == "updated"
    assert service.updated == [(document_id, "versión Git nueva", baseline_revision)]
    assert new_state["documents"]["README.md"]["source_sha256"] == hashlib.sha256(
        "versión Git nueva".encode()
    ).hexdigest()


@pytest.mark.asyncio
async def test_manual_siyuan_change_is_conflict_without_writing(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("Git estable", encoding="utf-8")
    path = publisher.siyuan_path(document, tmp_path)
    service = FakeService({path: "edición manual"})
    state = {
        "version": 1,
        "documents": {
            "README.md": {
                "path": path,
                "document_id": service.documents[path]["document_id"],
                "source_sha256": hashlib.sha256(b"Git estable").hexdigest(),
                "siyuan_revision_sha256": hashlib.sha256(b"baseline").hexdigest(),
            }
        },
    }

    manifest, new_state = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        state=state,
    )

    assert manifest[0]["status"] == "conflict"
    assert service.updated == []
    assert new_state == state


@pytest.mark.asyncio
async def test_force_conflict_explicitly_makes_git_win(tmp_path) -> None:
    document = tmp_path / "README.md"
    document.write_text("Git autoritativo", encoding="utf-8")
    path = publisher.siyuan_path(document, tmp_path)
    service = FakeService({path: "edición manual"})

    manifest, state = await publisher.publish_documents(
        [document],
        tmp_path,
        service,
        apply=True,
        force_conflicts=True,
        state={"version": 1, "documents": {}},
    )

    assert manifest[0]["status"] == "updated"
    assert manifest[0]["forced"] is True
    assert len(service.updated) == 1
    assert state["documents"]["README.md"]["source_sha256"] == hashlib.sha256(
        b"Git autoritativo"
    ).hexdigest()


@pytest.mark.asyncio
async def test_missing_git_source_is_reported_as_orphan_without_deletion(tmp_path) -> None:
    state = {
        "version": 1,
        "documents": {
            "docs/OLD.md": {
                "path": "/Growen/Documentación técnica/docs/OLD",
                "document_id": "20260827123456-abcdefg",
                "source_sha256": "a" * 64,
                "siyuan_revision_sha256": "b" * 64,
            }
        },
    }

    manifest, new_state = await publisher.publish_documents(
        [],
        tmp_path,
        FakeService(),
        apply=True,
        state=state,
    )

    assert manifest == [
        {
            "source": "docs/OLD.md",
            "path": "/Growen/Documentación técnica/docs/OLD",
            "status": "orphaned",
        }
    ]
    assert new_state == state


def test_write_state_atomic_persists_hashes_without_document_content(tmp_path) -> None:
    state_path = tmp_path / "publish-state.json"
    state = {
        "version": 1,
        "documents": {
            "README.md": {
                "path": "/Growen/Documentación técnica/README",
                "document_id": "20260827123456-abcdefg",
                "source_sha256": "a" * 64,
                "siyuan_revision_sha256": "b" * 64,
            }
        },
    }

    publisher.write_state_atomic(state_path, state)

    assert json.loads(state_path.read_text(encoding="utf-8")) == state
    assert "markdown" not in state_path.read_text(encoding="utf-8")


def test_state_file_lock_rejects_a_concurrent_publisher(tmp_path) -> None:
    state_path = tmp_path / "publish-state.json"

    with publisher.state_file_lock(state_path):
        with pytest.raises(publisher.PublisherLockedError, match="siyuan_publish_locked"):
            with publisher.state_file_lock(state_path):
                pass

    with publisher.state_file_lock(state_path):
        pass


def test_parse_arguments_requires_exact_confirmation_for_applied_rebuild() -> None:
    with pytest.raises(SystemExit):
        publisher.parse_arguments(["--apply", "--rebuild"])

    args = publisher.parse_arguments(
        [
            "--apply",
            "--rebuild",
            "--confirm-rebuild",
            "/Growen/Documentación técnica",
        ]
    )

    assert args.apply is True
    assert args.rebuild is True


def test_parse_arguments_allows_rebuild_dry_run_without_confirmation() -> None:
    args = publisher.parse_arguments(["--rebuild"])

    assert args.apply is False
    assert args.confirm_rebuild is None
