#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: publish_docs_to_siyuan.py
# NG-HEADER: Ubicación: scripts/publish_docs_to_siyuan.py
# NG-HEADER: Descripción: Publicación inicial create-only de documentación Git hacia SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.siyuan_server.client import SiYuanClient
from mcp_servers.siyuan_server.settings import SiYuanSettings, load_api_token
from mcp_servers.siyuan_server.tools import DocumentExistsError, SiYuanService


EXCLUDED_PARTS = {"archive", "superpowers", "Promps", "__pycache__"}
EXCLUDED_PREFIXES = ("RETROSPECTIVE_", "TEST_RESULTS_")


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
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for document in documents:
        content = document.read_text(encoding="utf-8")
        destination = siyuan_path(document, root)
        entry: dict[str, Any] = {
            "source": document.relative_to(root).as_posix(),
            "path": destination,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "status": "planned",
        }
        if apply:
            try:
                created = await service.create_document(destination, content)
                entry["status"] = "created"
                entry["document_id"] = created["document_id"]
            except DocumentExistsError:
                entry["status"] = "skipped"
            except Exception as exc:  # noqa: BLE001 - el manifiesto sólo registra el tipo seguro
                entry["status"] = "error"
                entry["error"] = type(exc).__name__
        manifest.append(entry)
    return manifest


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
            allowed_path_prefix=settings.allowed_path_prefix,
        )
        manifest = await publish_documents(discover_documents(root), root, service, apply=args.apply)
    output = Path(args.manifest)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {status: sum(1 for item in manifest if item["status"] == status) for status in {item["status"] for item in manifest}}
    print(json.dumps({"manifest": str(output), "counts": counts}, ensure_ascii=False))
    return 1 if counts.get("error", 0) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica documentación vigente en SiYuan sin sobrescribir.")
    parser.add_argument("--apply", action="store_true", help="Crea documentos; sin esta opción sólo planifica.")
    parser.add_argument("--manifest", default="logs/siyuan-publish-manifest.json")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DocumentExistsError", "discover_documents", "publish_documents", "siyuan_path"]
