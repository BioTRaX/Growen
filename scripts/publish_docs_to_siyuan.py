#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: publish_docs_to_siyuan.py
# NG-HEADER: Ubicación: scripts/publish_docs_to_siyuan.py
# NG-HEADER: Descripción: Sincronización unidireccional y segura de documentación Git hacia SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.siyuan_server.client import SiYuanClient  # noqa: E402
from mcp_servers.siyuan_server.settings import SiYuanSettings, load_api_token  # noqa: E402
from mcp_servers.siyuan_server.tools import SiYuanService  # noqa: E402


PUBLICATION_ROOT = "/Growen/Documentación técnica"
ROOT_DOCUMENTS = ("README.md", "Roadmap.md", "CHANGELOG.md", "AGENTS.md")


class PublisherLockedError(RuntimeError):
    pass


class GitDocumentsDirtyError(RuntimeError):
    pass


class DocumentationSecretError(RuntimeError):
    pass


@contextmanager
def state_file_lock(state_path: Path) -> Iterator[None]:
    lock_path = Path(f"{state_path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise PublisherLockedError("siyuan_publish_locked") from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def siyuan_path(document: Path, root: Path) -> str:
    relative = document.relative_to(root).with_suffix("").as_posix()
    return f"/Growen/Documentación técnica/{relative}"


def discover_documents(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", *ROOT_DOCUMENTS, "docs"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = [
        root / relative
        for relative in completed.stdout.splitlines()
        if relative.casefold().endswith(".md") and (root / relative).is_file()
    ]
    return sorted(
        set(result),
        key=lambda item: (
            len(item.relative_to(root).parts),
            item.relative_to(root).as_posix().lower(),
        ),
    )


def git_revision(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def assert_governed_documents_clean(root: Path) -> None:
    dirty: set[str] = set()
    pathspec = [*ROOT_DOCUMENTS, "docs"]
    for arguments in (
        ("diff", "--name-only", "--", *pathspec),
        ("diff", "--cached", "--name-only", "--", *pathspec),
        ("ls-files", "--others", "--exclude-standard", "--", *pathspec),
    ):
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        dirty.update(
            path for path in completed.stdout.splitlines() if path.casefold().endswith(".md")
        )
    if dirty:
        raise GitDocumentsDirtyError("git_documents_dirty")


def assert_no_document_secrets(documents: Iterable[Path]) -> None:
    patterns = (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    )
    for document in documents:
        content = document.read_text(encoding="utf-8")
        if any(pattern.search(content) for pattern in patterns):
            raise DocumentationSecretError("documentation_secret_detected")


def finalize_rebuild_after_resume(
    state: dict[str, Any],
    manifest: Iterable[dict[str, Any]],
    documents: Iterable[Path],
    root: Path,
    *,
    git_commit: str,
) -> dict[str, Any]:
    next_state = deepcopy(state)
    rebuild = next_state.get("rebuild")
    if not isinstance(rebuild, dict) or rebuild.get("phase") != "recreating":
        return next_state
    entries = list(manifest)
    active_sources = {document.relative_to(root).as_posix() for document in documents}
    if (
        any(entry.get("status") in {"error", "conflict", "orphaned"} for entry in entries)
        or set(next_state.get("documents", {})) != active_sources
    ):
        return next_state
    rebuild["phase"] = "complete"
    next_state["last_publish_commit"] = git_commit
    return next_state


async def rebuild_documents(
    documents: Iterable[Path],
    root: Path,
    service: SiYuanService,
    *,
    apply: bool,
    confirmation: str | None,
    git_commit: str,
    state: dict[str, Any],
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    documents = list(documents)
    root_document_id = await service.find_document_by_path(PUBLICATION_ROOT)
    if not root_document_id:
        raise ValueError("siyuan_publication_root_missing")

    control_entry: dict[str, Any] = {
        "source": "@rebuild",
        "path": PUBLICATION_ROOT,
        "document_id": root_document_id,
        "status": "planned_delete",
    }
    if not apply:
        planned = [control_entry]
        for document in documents:
            content = document.read_text(encoding="utf-8")
            planned.append(
                {
                    "source": document.relative_to(root).as_posix(),
                    "path": siyuan_path(document, root),
                    "source_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "status": "planned_create",
                }
            )
        return planned, state

    if confirmation != PUBLICATION_ROOT:
        raise ValueError("rebuild_confirmation_invalid")

    next_state: dict[str, Any] = {
        "version": 1,
        "documents": {},
        "last_publish_commit": git_commit,
        "rebuild": {
            "path": PUBLICATION_ROOT,
            "phase": "deleting",
            "source_count": len(documents),
        },
    }
    if checkpoint is not None:
        checkpoint(next_state)
    await service.remove_git_document_tree(PUBLICATION_ROOT, root_document_id)
    next_state["rebuild"].update(
        phase="recreating",
        deleted_document_id=root_document_id,
    )
    if checkpoint is not None:
        checkpoint(next_state)

    published, next_state = await publish_documents(
        documents,
        root,
        service,
        apply=True,
        state=next_state,
        checkpoint=checkpoint,
    )
    control_entry["status"] = "deleted"
    if not any(entry["status"] in {"error", "conflict"} for entry in published):
        next_state["rebuild"]["phase"] = "complete"
        if checkpoint is not None:
            checkpoint(next_state)
    return [control_entry, *published], next_state


async def publish_documents(
    documents: Iterable[Path],
    root: Path,
    service: SiYuanService,
    *,
    apply: bool,
    state: dict[str, Any],
    force_conflicts: bool = False,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if force_conflicts and not apply:
        raise ValueError("force_conflicts_requires_apply")
    manifest: list[dict[str, Any]] = []
    next_state = deepcopy(state)
    state_documents = next_state.setdefault("documents", {})

    def record_baseline(source: str, baseline: dict[str, str]) -> None:
        state_documents[source] = baseline
        if checkpoint is not None:
            checkpoint(next_state)

    active_sources: set[str] = set()
    for document in documents:
        content = document.read_text(encoding="utf-8")
        destination = siyuan_path(document, root)
        source = document.relative_to(root).as_posix()
        active_sources.add(source)
        source_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        entry: dict[str, Any] = {
            "source": source,
            "path": destination,
            "source_sha256": source_sha256,
        }
        try:
            document_id = await service.find_document_by_path(destination)
            baseline = state_documents.get(source)
            if not document_id:
                entry["status"] = "planned_create"
                if apply:
                    created = await service.create_git_document(destination, content)
                    document_id = str(created["document_id"])
                    current = await service.read_document(document_id)
                    entry.update(status="created", document_id=document_id)
                    record_baseline(source, {
                        "path": destination,
                        "document_id": document_id,
                        "source_sha256": source_sha256,
                        "siyuan_revision_sha256": current["revision_sha256"],
                    })
                manifest.append(entry)
                continue

            current = await service.read_document(document_id)
            current_revision = str(current["revision_sha256"])
            entry["document_id"] = document_id
            if baseline is None:
                if current_revision == source_sha256:
                    entry["status"] = "unchanged"
                    if apply:
                        record_baseline(source, {
                            "path": destination,
                            "document_id": document_id,
                            "source_sha256": source_sha256,
                            "siyuan_revision_sha256": current_revision,
                        })
                elif not force_conflicts:
                    entry["status"] = "conflict"
                else:
                    updated = await service.update_git_document(
                        document_id,
                        content,
                        current_revision,
                    )
                    entry.update(status="updated", forced=True)
                    record_baseline(source, {
                        "path": destination,
                        "document_id": document_id,
                        "source_sha256": source_sha256,
                        "siyuan_revision_sha256": updated["revision_sha256"],
                    })
                manifest.append(entry)
                continue

            source_changed = baseline.get("source_sha256") != source_sha256
            siyuan_changed = baseline.get("siyuan_revision_sha256") != current_revision
            if not source_changed and not siyuan_changed:
                entry["status"] = "unchanged"
            elif source_changed and not siyuan_changed:
                entry["status"] = "planned_update"
                if apply:
                    updated = await service.update_git_document(
                        document_id,
                        content,
                        current_revision,
                    )
                    entry["status"] = "updated"
                    record_baseline(source, {
                        "path": destination,
                        "document_id": document_id,
                        "source_sha256": source_sha256,
                        "siyuan_revision_sha256": updated["revision_sha256"],
                    })
            elif not force_conflicts:
                entry["status"] = "conflict"
            else:
                updated = await service.update_git_document(
                    document_id,
                    content,
                    current_revision,
                )
                entry.update(status="updated", forced=True)
                record_baseline(source, {
                    "path": destination,
                    "document_id": document_id,
                    "source_sha256": source_sha256,
                    "siyuan_revision_sha256": updated["revision_sha256"],
                })
        except Exception as exc:  # noqa: BLE001 - el manifiesto sólo registra el tipo seguro
            entry["status"] = "error"
            entry["error"] = type(exc).__name__
        manifest.append(entry)

    for source, baseline in state.get("documents", {}).items():
        if source in active_sources:
            continue
        manifest.append(
            {
                "source": source,
                "path": baseline["path"],
                "status": "orphaned",
            }
        )
    return manifest, next_state


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "documents": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("documents"), dict):
        raise ValueError("siyuan_publish_state_invalid")
    return data


def write_state_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


async def _run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    documents = discover_documents(root)
    assert_governed_documents_clean(root)
    assert_no_document_secrets(documents)
    current_commit = git_revision(root)
    settings = SiYuanSettings.from_env()
    client = SiYuanClient(
        base_url=settings.base_url,
        token_provider=load_api_token,
        timeout_seconds=settings.timeout_seconds,
    )
    async with client:
        service = SiYuanService(
            client=client,
            notebook_name=settings.notebook_name,
            notebook_id=settings.notebook_id,
            git_path_prefix=settings.allowed_path_prefix,
            private_path_prefixes=settings.private_path_prefixes,
            visible_path_prefixes=(settings.allowed_path_prefix,),
        )
        state_path = Path(args.state)
        if not state_path.is_absolute():
            state_path = root / state_path
        with state_file_lock(state_path):
            previous_state = load_state(state_path)
            checkpoint = (
                (lambda current: write_state_atomic(state_path, current))
                if args.apply
                else None
            )
            if args.rebuild:
                manifest, state = await rebuild_documents(
                    documents,
                    root,
                    service,
                    apply=args.apply,
                    confirmation=args.confirm_rebuild,
                    git_commit=current_commit,
                    state=previous_state,
                    checkpoint=checkpoint,
                )
            else:
                manifest, state = await publish_documents(
                    documents,
                    root,
                    service,
                    apply=args.apply,
                    force_conflicts=args.force_conflicts,
                    state=previous_state,
                    checkpoint=checkpoint,
                )
                if args.apply:
                    state = finalize_rebuild_after_resume(
                        state,
                        manifest,
                        documents,
                        root,
                        git_commit=current_commit,
                    )
                    if not any(
                        entry["status"] in {"error", "conflict", "orphaned"}
                        for entry in manifest
                    ):
                        state["last_publish_commit"] = current_commit
            if args.apply:
                write_state_atomic(state_path, state)
    output = Path(args.manifest)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {status: sum(1 for item in manifest if item["status"] == status) for status in {item["status"] for item in manifest}}
    print(json.dumps({"manifest": str(output), "counts": counts}, ensure_ascii=False))
    return 1 if counts.get("error", 0) or counts.get("conflict", 0) else 0


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincroniza documentación Git hacia SiYuan con control de conflictos.")
    parser.add_argument("--apply", action="store_true", help="Aplica operaciones seguras; sin esta opción sólo planifica.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Planifica o reconstruye la raíz técnica completa desde Git.",
    )
    parser.add_argument(
        "--confirm-rebuild",
        help=f"Confirmación exacta requerida al aplicar rebuild: {PUBLICATION_ROOT}",
    )
    parser.add_argument(
        "--force-conflicts",
        action="store_true",
        help="Con --apply, confirma que Git sobrescriba divergencias después de crear historial.",
    )
    parser.add_argument("--manifest", default="logs/siyuan-publish-manifest.json")
    parser.add_argument(
        "--state",
        default=os.getenv("SIYUAN_PUBLISH_STATE_FILE", "../growen-siyuan/publish-state.json"),
    )
    args = parser.parse_args(argv)
    if args.rebuild and args.force_conflicts:
        parser.error("--force-conflicts no se combina con --rebuild")
    if args.apply and args.rebuild and args.confirm_rebuild != PUBLICATION_ROOT:
        parser.error(f"--confirm-rebuild debe ser exactamente {PUBLICATION_ROOT}")
    if args.confirm_rebuild is not None and not (args.apply and args.rebuild):
        parser.error("--confirm-rebuild sólo se usa con --apply --rebuild")
    return args


def main() -> int:
    return asyncio.run(_run(parse_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "discover_documents",
    "finalize_rebuild_after_resume",
    "git_revision",
    "load_state",
    "parse_arguments",
    "PublisherLockedError",
    "publish_documents",
    "rebuild_documents",
    "siyuan_path",
    "state_file_lock",
    "write_state_atomic",
]
