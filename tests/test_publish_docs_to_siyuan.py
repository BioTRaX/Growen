#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_publish_docs_to_siyuan.py
# NG-HEADER: Ubicación: tests/test_publish_docs_to_siyuan.py
# NG-HEADER: Descripción: Pruebas de sincronización segura de Markdown Git hacia SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
        document_id = "20260827123456-abcdefg"
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


def test_siyuan_path_preserves_repository_structure() -> None:
    root = Path("C:/repo")

    assert publisher.siyuan_path(root / "README.md", root) == "/Growen/Documentación técnica/README"
    assert publisher.siyuan_path(root / "docs" / "MCP.md", root) == "/Growen/Documentación técnica/docs/MCP"


def test_discover_documents_excludes_archive_and_generated_plans(tmp_path) -> None:
    (tmp_path / "README.md").write_text("root", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "MCP.md").write_text("mcp", encoding="utf-8")
    (tmp_path / "docs" / "archive").mkdir()
    (tmp_path / "docs" / "archive" / "OLD.md").write_text("old", encoding="utf-8")
    (tmp_path / "docs" / "superpowers").mkdir()
    (tmp_path / "docs" / "superpowers" / "PLAN.md").write_text("plan", encoding="utf-8")

    documents = publisher.discover_documents(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in documents] == ["README.md", "docs/MCP.md"]


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
