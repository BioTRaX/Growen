#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: server.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/server.py
# NG-HEADER: Descripción: Definición compartida de tools FastMCP para SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

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
            return [tool for tool in tools if tool.name != "create_siyuan_document"]
        return []


mcp = RoleAwareFastMCP(
    "Growen SiYuan",
    instructions=(
        "Documentación Nice Grow. Buscar y leer antes de crear. Las escrituras sólo pueden hacerse "
        "bajo /Growen, no sobrescriben documentos y requieren aprobación. No existen tools de SQL libre, "
        "actualización, movimiento o eliminación."
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


async def _execute(method: str, **kwargs: Any) -> dict[str, Any]:
    client, settings = _configured_client()
    async with client:
        service = SiYuanService(
            client=client,
            notebook_name=settings.notebook_name,
            notebook_id=settings.notebook_id,
            allowed_path_prefix=settings.allowed_path_prefix,
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
    """Crea sin sobrescribir una página Markdown bajo el prefijo autorizado."""
    await _authorize("create_siyuan_document", write=True)
    return await _execute("create_document", path=path, markdown=markdown)


__all__ = [
    "create_siyuan_document",
    "list_siyuan_notebooks",
    "mcp",
    "read_siyuan_document",
    "search_siyuan_docs",
]
