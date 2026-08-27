#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: main.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/main.py
# NG-HEADER: Descripción: Transporte HTTP autenticado del MCP de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .settings import load_mcp_secret

load_dotenv()

try:
    os.environ["MCP_SECRET_KEY"] = load_mcp_secret()
except Exception:  # La aplicación conserva un error seguro al validar el primer JWT.
    os.environ["MCP_SECRET_KEY"] = os.getenv("MCP_SECRET_KEY", "")
os.environ["MCP_SECRET_KEY_PREVIOUS"] = os.getenv("MCP_SIYUAN_SECRET_KEY_PREVIOUS", "")
os.environ["MCP_JWT_AUDIENCE"] = os.getenv("MCP_SIYUAN_JWT_AUDIENCE", "growen-mcp-siyuan")
os.environ["MCP_JWT_KEY_ID"] = os.getenv("MCP_SIYUAN_KEY_ID", "siyuan-v1")
os.environ["MCP_JWT_PREVIOUS_KEY_ID"] = os.getenv("MCP_SIYUAN_PREVIOUS_KEY_ID", "")

from mcp_servers.security import MCPBearerContextMiddleware  # noqa: E402

from .client import SiYuanClient  # noqa: E402
from .server import mcp  # noqa: E402
from .settings import SiYuanSettings, load_api_token  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


http_app = FastAPI(title="Growen MCP SiYuan", version="1.0.0", lifespan=lifespan)


async def check_siyuan_health() -> None:
    settings = SiYuanSettings.from_env()
    async with SiYuanClient(
        base_url=settings.base_url,
        token_provider=load_api_token,
        timeout_seconds=settings.timeout_seconds,
    ) as client:
        await client.post("/api/system/version", {}, retry_read=True)


@http_app.get("/health")
async def health():
    try:
        await check_siyuan_health()
    except Exception:  # noqa: BLE001 - el health no filtra detalles del upstream
        return JSONResponse(
            {"status": "degraded", "service": "mcp_siyuan", "upstream": "unavailable"},
            status_code=503,
        )
    return {"status": "ok", "service": "mcp_siyuan", "upstream": "siyuan", "endpoint": "/mcp"}


@http_app.get("/")
async def root():
    return {"status": "ok", "service": "mcp_siyuan"}


http_app.mount("/mcp", mcp.streamable_http_app())
app = MCPBearerContextMiddleware(http_app)
