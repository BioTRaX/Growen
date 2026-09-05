#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: smoke_siyuan_mcp.py
# NG-HEADER: Ubicación: scripts/smoke_siyuan_mcp.py
# NG-HEADER: Descripción: Smoke real de lectura, creación y relectura en SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.siyuan_server.client import SiYuanClient  # noqa: E402
from mcp_servers.siyuan_server.settings import SiYuanSettings, load_api_token  # noqa: E402
from mcp_servers.siyuan_server.tools import DocumentConflictError, SiYuanService  # noqa: E402


SMOKE_MARKDOWN = "# Prueba MCP SiYuan\n\nDocumento creado automáticamente para verificar lectura y escritura."
SMOKE_UPDATED_MARKDOWN = (
    "# Prueba MCP SiYuan\n\nDocumento actualizado automáticamente para verificar concurrencia optimista."
)


async def run_smoke(service: SiYuanService, *, timestamp: str | None = None) -> dict[str, str]:
    notebooks = await service.list_notebooks()
    if not notebooks.get("items"):
        raise RuntimeError("siyuan_notebook_missing")
    # La instalación nueva puede no contener aún README; la nota inicial
    # publicada por el bootstrap sirve como evidencia de lectura existente.
    searched = await service.search_documents("Nota", limit=20)
    if not searched.get("items"):
        raise RuntimeError("siyuan_existing_document_missing")
    existing_id = searched["items"][0]["document_id"]
    await service.read_document(existing_id)
    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"/Operación/Pruebas MCP/{stamp}"
    created = await service.create_document(path, SMOKE_MARKDOWN)
    initial = await service.read_document(created["document_id"])
    await service.update_document(
        created["document_id"],
        SMOKE_UPDATED_MARKDOWN,
        initial["revision_sha256"],
    )
    try:
        await service.update_document(
            created["document_id"],
            "contenido que no debe escribirse",
            initial["revision_sha256"],
        )
    except DocumentConflictError:
        conflict_verified = True
    else:
        raise RuntimeError("siyuan_smoke_conflict_missing")
    reread = await service.read_document(created["document_id"])
    # SiYuan agrega frontmatter y el título derivado de la ruta al exportar;
    # verificamos que el cuerpo escrito permanezca íntegro.
    if SMOKE_UPDATED_MARKDOWN.strip() not in reread["markdown"]:
        raise RuntimeError("siyuan_smoke_content_mismatch")
    return {
        "status": "ok",
        "existing_document_id": existing_id,
        "created_document_id": created["document_id"],
        "created_path": path,
        "conflict_verified": conflict_verified,
    }


async def _main() -> int:
    settings = SiYuanSettings.from_env()
    async with SiYuanClient(
        base_url=settings.base_url,
        token_provider=load_api_token,
        timeout_seconds=settings.timeout_seconds,
    ) as client:
        service = SiYuanService(
            client=client,
            notebook_name=settings.notebook_name,
            notebook_id=settings.notebook_id,
            git_path_prefix=settings.allowed_path_prefix,
            private_path_prefixes=settings.private_path_prefixes,
            visible_path_prefixes=(
                settings.allowed_path_prefix,
                *settings.private_path_prefixes,
            ),
        )
        result = await run_smoke(service)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))


__all__ = ["SMOKE_MARKDOWN", "SMOKE_UPDATED_MARKDOWN", "run_smoke"]
