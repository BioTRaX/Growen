#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: main.py
# NG-HEADER: Ubicación: mcp_servers/products_server/main.py
# NG-HEADER: Descripción: Punto de entrada FastAPI para servidor MCP de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Any, Dict
import os
import logging

from .tools import invoke_tool, PermissionError
import httpx

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("mcp_products.main")


app = FastAPI(title="Growen MCP Products Server", version="0.1.0")


class InvokeRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


class InvokeResponse(BaseModel):
    tool_name: str
    result: Dict[str, Any]


@app.post("/invoke_tool", response_model=InvokeResponse)
async def invoke_tool_endpoint(
    payload: InvokeRequest,
    x_mcp_token: str | None = Header(
        default=None,
        alias="X-MCP-Token",
        convert_underscores=False,
    ),
    x_mcp_token_lower: str | None = Header(
        default=None,
        alias="x-mcp-token",
        convert_underscores=False,
    ),
):
    """Invoca una herramienta registrada en el servidor MCP.

    Manejo de errores:
    - 404 si tool desconocida
    - 403 si permiso insuficiente
    - 400 para validaciones genéricas
    - 502 para errores de red hacia la API backend
    """
    # Lectura dinámica de configuración de token en cada request para permitir cambios en runtime/tests
    require_token = os.getenv("MCP_REQUIRE_TOKEN", "0") == "1"
    shared_token = os.getenv("MCP_SHARED_TOKEN", "")
    token_value = x_mcp_token or x_mcp_token_lower
    if require_token:
        if not token_value or token_value != shared_token:
            raise HTTPException(status_code=401, detail="Token MCP inválido o ausente")
    try:
        result = await invoke_tool(payload.tool_name, payload.parameters)
        logger.debug("Tool %s ejecutada OK", payload.tool_name)
        return InvokeResponse(tool_name=payload.tool_name, result=result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:  # tipo propio
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.TimeoutException as e:  # noqa: PERF203
        logger.warning("Timeout consultando backend para tool=%s: %s", payload.tool_name, e)
        raise HTTPException(status_code=504, detail="Timeout al consultar API backend") from e
    except httpx.RequestError as e:
        logger.warning("Error de red consultando backend tool=%s: %s", payload.tool_name, e)
        raise HTTPException(status_code=502, detail="Error de red hacia API backend") from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Fallo ejecutando tool %s", payload.tool_name)
        raise HTTPException(status_code=502, detail=f"Error upstream o interno: {e}") from e


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp_products"}


# Para ejecución local: uvicorn mcp_servers.products_server.main:app --reload --port 8100
