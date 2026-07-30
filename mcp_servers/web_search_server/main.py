#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: main.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/main.py
# NG-HEADER: Descripción: Servidor MCP real y adaptador RPC de búsqueda web.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()
os.environ["MCP_SECRET_KEY"] = os.getenv("MCP_WEB_SEARCH_SECRET_KEY", os.getenv("MCP_SECRET_KEY", ""))
os.environ["MCP_SECRET_KEY_PREVIOUS"] = os.getenv("MCP_WEB_SEARCH_SECRET_KEY_PREVIOUS", "")
os.environ["MCP_JWT_AUDIENCE"] = os.getenv("MCP_WEB_SEARCH_JWT_AUDIENCE", "growen-mcp-web-search")
os.environ["MCP_JWT_KEY_ID"] = os.getenv("MCP_WEB_SEARCH_KEY_ID", "web-search-v1")
os.environ["MCP_JWT_PREVIOUS_KEY_ID"] = os.getenv("MCP_WEB_SEARCH_PREVIOUS_KEY_ID", "")

from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from mcp_servers.security import (  # noqa: E402
    MCPAuthError,
    MCPBearerContextMiddleware,
    MCPRateLimited,
    MCPUnauthorized,
    get_current_claims,
    get_current_token,
    mcp_transport_security,
)
from .tools import (  # noqa: E402
    fetch_web_document as execute_fetch_web_document,
    invoke_tool,
    search_web as execute_search_web,
)
from agent_core.chat_policy import tool_allowed  # noqa: E402

logger = logging.getLogger("mcp_web_search.main")
_legacy_invocations_total = 0


class RoleAwareFastMCP(FastMCP):
    async def list_tools(self):
        """Expone búsqueda web únicamente a roles internos autorizados."""
        tools = await super().list_tools()
        claims = get_current_claims()
        return [tool for tool in tools if tool_allowed(tool.name, claims.role, claims.channel)]


mcp = RoleAwareFastMCP(
    "Growen Web Search",
    instructions="Búsqueda web externa controlada para usuarios internos autorizados.",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=mcp_transport_security(
        ["mcp_web_search:*", "growen-mcp-web-search:*"]
    ),
)


class WebSearchOutput(BaseModel):
    items: list[dict]
    query: str
    source: str | None = None
    error: str | None = None


class WebDocumentOutput(BaseModel):
    url: str
    mime_type: str
    text: str
    content_hash: str
    bytes: int
    redirects: list[str]


@mcp.tool()
async def search_web(query: str, max_results: int = 5) -> WebSearchOutput:
    """Busca fuentes web; requiere rol admin o colaborador y retorna hasta 10 resultados."""
    return WebSearchOutput.model_validate(
        await execute_search_web(get_current_token(), query=query, max_results=max_results)
    )


@mcp.tool()
async def fetch_web_document(url: str) -> WebDocumentOutput:
    """Lee una fuente HTTPS pública en HTML o PDF aplicando controles SSRF y de tamaño."""
    return WebDocumentOutput.model_validate(
        await execute_fetch_web_document(get_current_token(), url=url)
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


legacy_app = FastAPI(title="Growen MCP Web Search", version="1.0.0", lifespan=lifespan)


class InvokePayload(BaseModel):
    tool_name: str
    parameters: dict


@legacy_app.post("/invoke_tool", deprecated=True)
async def invoke_legacy(
    payload: InvokePayload,
    authorization: str | None = Header(default=None),
    x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
):
    global _legacy_invocations_total
    if os.getenv("MCP_LEGACY_RPC_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=410, detail="RPC MCP legacy deshabilitado")
    bearer = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    token = bearer or x_mcp_token
    if not token:
        raise HTTPException(status_code=401, detail="Token MCP requerido")
    try:
        _legacy_invocations_total += 1
        logger.warning("Invocación RPC legacy recibida para tool=%s", payload.tool_name)
        result = await invoke_tool(payload.tool_name, payload.parameters, token)
        return {"tool_name": payload.tool_name, "result": result}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MCPUnauthorized as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MCPRateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": str(exc)},
            headers={"Retry-After": "60"},
        ) from exc
    except MCPAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Fallo en tool web legacy")
        raise HTTPException(status_code=502, detail="tool failure") from exc


@legacy_app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mcp_web_search",
        "protocol": "mcp",
        "protocol_version": os.getenv("MCP_PROTOCOL_VERSION", "2025-11-25"),
        "endpoint": "/mcp",
        "legacy_invocations_total": _legacy_invocations_total,
    }


legacy_app.mount("/mcp", mcp.streamable_http_app())
app = MCPBearerContextMiddleware(legacy_app)
