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
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.siyuan_server.client import SiYuanClient  # noqa: E402
from mcp_servers.siyuan_server.settings import SiYuanSettings, load_api_token  # noqa: E402
from mcp_servers.siyuan_server.tools import SiYuanService  # noqa: E402


EXCLUDED_PARTS = {"archive", "superpowers", "Promps", "__pycache__"}
EXCLUDED_PREFIXES = ("RETROSPECTIVE_", "TEST_RESULTS_")


class PublisherLockedError(RuntimeError):
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
    candidates = [root / "README.md", root / "Roadmap.md", root / "CHANGELOG.md", root / "AGENTS.md"]
    docs_root = root / "docs"
    if docs_root.exists():
        candidates.extend(docs_root.rglob("*.md"))
    result = []
    for path in candidates:
        relative_parts = set(path.relative_to(root).parts)
        if not path.is_file() or relative_parts & EXCLUDED_PARTS:
            continue
        if path.name.startswith(EXCLUDED_PREFIXES):
            continue
        result.append(path)
    return sorted(
        set(result),
        key=lambda item: (
            len(item.relative_to(root).parts),
            item.relative_to(root).as_posix().lower(),
        ),
    )


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
            manifest, state = await publish_documents(
                discover_documents(root),
                root,
                service,
                apply=args.apply,
                force_conflicts=args.force_conflicts,
                state=load_state(state_path),
                checkpoint=(
                    (lambda current: write_state_atomic(state_path, current))
                    if args.apply
                    else None
                ),
            )
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza documentación Git hacia SiYuan con control de conflictos.")
    parser.add_argument("--apply", action="store_true", help="Aplica operaciones seguras; sin esta opción sólo planifica.")
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
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "discover_documents",
    "load_state",
    "PublisherLockedError",
    "publish_documents",
    "siyuan_path",
    "state_file_lock",
    "write_state_atomic",
]
