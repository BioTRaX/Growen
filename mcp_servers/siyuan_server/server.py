#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: server.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/server.py
# NG-HEADER: Descripción: Definición compartida de tools FastMCP para SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_servers.security import (
    MCPAuthError,
    MCPRateLimited,
    MCPUnauthorized,
    check_rate_limit,
    get_current_claims,
    log_audit,
    mcp_transport_security,
)

from .client import SiYuanClient
from .settings import SiYuanSettings, load_api_token
from .tools import SiYuanService


READ_ROLES = {"admin", "colaborador"}
WRITE_ROLES = {"admin"}
WRITE_TOOL_NAMES = {
    "create_siyuan_document",
    "create_siyuan_task_database",
    "update_siyuan_document",
}
_audit_logger = logging.getLogger("growen.mcp.audit")


def _claims_or_none():
    try:
        return get_current_claims()
    except MCPAuthError:
        return None


class RoleAwareFastMCP(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()
        claims = _claims_or_none()
        if claims is None:
            return tools
        if claims.role == "admin":
            return tools
        if claims.role == "colaborador":
            return [tool for tool in tools if tool.name not in WRITE_TOOL_NAMES]
        return []


mcp = RoleAwareFastMCP(
    "Growen SiYuan",
    instructions=(
        "Documentación Nice Grow. Git gobierna /Growen; las escrituras MCP sólo pueden hacerse "
        "en las áreas privadas configuradas y requieren aprobación. Las actualizaciones exigen la "
        "revisión SHA-256 leída previamente. No existen tools de SQL libre, movimiento o eliminación."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=mcp_transport_security(["mcp_siyuan:*", "growen-mcp-siyuan:*"]),
)


async def _authorize(tool_name: str, *, write: bool) -> None:
    claims = _claims_or_none()
    if claims is None:
        return
    roles = WRITE_ROLES if write else READ_ROLES
    if claims.role not in roles:
        log_audit(claims.sub, tool_name, "unauthorized")
        raise MCPUnauthorized("Rol no autorizado para esta herramienta")
    if not await check_rate_limit(claims.sub):
        log_audit(claims.sub, tool_name, "rate_limited")
        raise MCPRateLimited("Límite de invocaciones MCP excedido")


def _configured_client() -> tuple[SiYuanClient, SiYuanSettings]:
    settings = SiYuanSettings.from_env()
    return (
        SiYuanClient(
            base_url=settings.base_url,
            token_provider=load_api_token,
            timeout_seconds=settings.timeout_seconds,
        ),
        settings,
    )


def _visible_path_prefixes(settings: SiYuanSettings) -> tuple[str, ...]:
    claims = _claims_or_none()
    if claims is None or claims.role == "admin":
        return (settings.allowed_path_prefix, *settings.private_path_prefixes)
    return (settings.allowed_path_prefix,)


async def _execute(method: str, **kwargs: Any) -> dict[str, Any]:
    client, settings = _configured_client()
    async with client:
        service = SiYuanService(
            client=client,
            notebook_name=settings.notebook_name,
            notebook_id=settings.notebook_id,
            git_path_prefix=settings.allowed_path_prefix,
            private_path_prefixes=settings.private_path_prefixes,
            visible_path_prefixes=_visible_path_prefixes(settings),
        )
        operation = getattr(service, method)
        return await operation(**kwargs)


READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
CREATE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
UPDATE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)


def _document_root(hpath: str | None) -> str | None:
    parts = str(hpath or "").split("/")
    return f"/{parts[1]}" if len(parts) > 1 and parts[1] else None


def _audit_document_write(
    *,
    tool_name: str,
    status: str,
    document_id: str | None = None,
    hpath: str | None = None,
    previous_revision_sha256: str | None = None,
    revision_sha256: str | None = None,
    error_code: str | None = None,
) -> None:
    claims = _claims_or_none()
    subject = claims.sub if claims else "local-stdio"
    entry: dict[str, Any] = {
        "event": "siyuan_document_write",
        "subject_hash": hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16],
        "tool_name": tool_name,
        "status": status,
    }
    if document_id:
        entry["document_id_hash"] = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:16]
    root = _document_root(hpath)
    if root:
        entry["document_root"] = root
    if previous_revision_sha256:
        entry["previous_revision_sha256"] = previous_revision_sha256
    if revision_sha256:
        entry["revision_sha256"] = revision_sha256
    if error_code:
        entry["error_code"] = error_code
    _audit_logger.info(json.dumps(entry, ensure_ascii=False, sort_keys=True))


@mcp.tool(annotations=READ_ANNOTATIONS)
async def list_siyuan_notebooks() -> dict[str, Any]:
    """Lista los notebooks visibles, sin devolver contenido documental."""
    await _authorize("list_siyuan_notebooks", write=False)
    return await _execute("list_notebooks")


@mcp.tool(annotations=READ_ANNOTATIONS)
async def search_siyuan_docs(query: str, limit: int = 20) -> dict[str, Any]:
    """Busca texto dentro del notebook configurado de Nice Grow."""
    await _authorize("search_siyuan_docs", write=False)
    return await _execute("search_documents", query=query, limit=limit)


@mcp.tool(annotations=READ_ANNOTATIONS)
async def read_siyuan_document(document_id: str) -> dict[str, Any]:
    """Lee un documento de SiYuan como Markdown por su ID."""
    await _authorize("read_siyuan_document", write=False)
    return await _execute("read_document", document_id=document_id)


@mcp.tool(annotations=CREATE_ANNOTATIONS)
async def create_siyuan_document(path: str, markdown: str) -> dict[str, Any]:
    """Crea sin sobrescribir una página Markdown en un área privada autorizada."""
    await _authorize("create_siyuan_document", write=True)
    try:
        result = await _execute("create_document", path=path, markdown=markdown)
    except Exception as exc:
        _audit_document_write(
            tool_name="create_siyuan_document",
            status="error",
            hpath=path,
            error_code=type(exc).__name__,
        )
        raise
    _audit_document_write(
        tool_name="create_siyuan_document",
        status="success",
        document_id=str(result.get("document_id") or ""),
        hpath=str(result.get("hpath") or path),
    )
    return result


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
async def create_siyuan_task_database(document_id: str) -> dict[str, Any]:
    """Añade a un documento privado una sección Tareas con una base estructurada."""
    await _authorize("create_siyuan_task_database", write=True)
    try:
        result = await _execute("create_task_database", document_id=document_id)
    except Exception as exc:
        _audit_document_write(
            tool_name="create_siyuan_task_database",
            status="error",
            document_id=document_id,
            error_code=type(exc).__name__,
        )
        raise
    _audit_document_write(
        tool_name="create_siyuan_task_database",
        status="success",
        document_id=document_id,
        hpath=str(result.get("hpath") or ""),
    )
    return result


@mcp.tool(annotations=UPDATE_ANNOTATIONS)
async def update_siyuan_document(
    document_id: str,
    markdown: str,
    expected_revision_sha256: str,
) -> dict[str, Any]:
    """Actualiza un documento privado si conserva la revisión SHA-256 esperada."""
    await _authorize("update_siyuan_document", write=True)
    try:
        result = await _execute(
            "update_document",
            document_id=document_id,
            markdown=markdown,
            expected_revision_sha256=expected_revision_sha256,
        )
    except Exception as exc:
        _audit_document_write(
            tool_name="update_siyuan_document",
            status="error",
            document_id=document_id,
            error_code=type(exc).__name__,
        )
        raise
    _audit_document_write(
        tool_name="update_siyuan_document",
        status="success",
        document_id=document_id,
        hpath=str(result.get("hpath") or ""),
        previous_revision_sha256=str(result.get("previous_revision_sha256") or ""),
        revision_sha256=str(result.get("revision_sha256") or ""),
    )
    return result


__all__ = [
    "create_siyuan_document",
    "create_siyuan_task_database",
    "list_siyuan_notebooks",
    "mcp",
    "read_siyuan_document",
    "search_siyuan_docs",
    "update_siyuan_document",
]
