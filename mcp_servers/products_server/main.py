#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: main.py
# NG-HEADER: Ubicación: mcp_servers/products_server/main.py
# NG-HEADER: Descripción: Punto de entrada FastAPI para servidor MCP de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict
import os
import logging

from dotenv import load_dotenv

load_dotenv()
os.environ["MCP_SECRET_KEY"] = os.getenv("MCP_PRODUCTS_SECRET_KEY", os.getenv("MCP_SECRET_KEY", ""))
os.environ["MCP_SECRET_KEY_PREVIOUS"] = os.getenv("MCP_PRODUCTS_SECRET_KEY_PREVIOUS", "")
os.environ["MCP_JWT_AUDIENCE"] = os.getenv("MCP_PRODUCTS_JWT_AUDIENCE", "growen-mcp-products")
os.environ["MCP_JWT_KEY_ID"] = os.getenv("MCP_PRODUCTS_KEY_ID", "products-v1")
os.environ["MCP_JWT_PREVIOUS_KEY_ID"] = os.getenv("MCP_PRODUCTS_PREVIOUS_KEY_ID", "")

from .tools import invoke_tool  # noqa: E402
from mcp_servers.security import (  # noqa: E402
    MCPAuthError,
    MCPTokenExpired,
    MCPTokenInvalid,
    MCPUnauthorized,
    MCPRateLimited,
    MCPBearerContextMiddleware,
    get_current_claims,
    get_current_token,
    mcp_transport_security,
)
import httpx  # noqa: E402

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("mcp_products.main")
_legacy_invocations_total = 0


class RoleAwareFastMCP(FastMCP):
    async def list_tools(self):
        """Evita revelar al cliente tools que su rol no puede ejecutar."""
        tools = await super().list_tools()
        role = get_current_claims().role
        allowed = {
            "find_products_by_name": {"guest", "colaborador", "admin"},
            "get_product_info": {"guest", "colaborador", "admin"},
            "get_product_full_info": {"colaborador", "admin"},
        }
        return [tool for tool in tools if role in allowed.get(tool.name, set())]


mcp = RoleAwareFastMCP(
    "Growen Products",
    instructions="Herramientas de lectura del catálogo interno de Growen.",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=mcp_transport_security(
        ["mcp_products:*", "growen-mcp-products:*"]
    ),
)


class ProductInfoOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: int | None = None
    sku: str | None = None
    name: str
    sale_price: float | None = None
    stock: int | float | None = None
    description: str | None = None
    technical_specs: dict[str, Any] | None = None
    usage_instructions: dict[str, Any] | None = None
    tags: list[str] | None = None
    images: list[dict[str, Any]] | None = None


class ProductSearchOutput(BaseModel):
    items: list[dict[str, Any]]
    count: int
    query: str


@mcp.tool()
async def find_products_by_name(query: str) -> ProductSearchOutput:
    """Busca productos por nombre, categoría o características."""
    from .tools import find_products_by_name as execute

    return ProductSearchOutput.model_validate(await execute(get_current_token(), query=query))


@mcp.tool()
async def get_product_info(sku: str | None = None, product_id: int | None = None) -> ProductInfoOutput:
    """Obtiene precio, stock y datos públicos por SKU canónico o ID de producto."""
    from .tools import get_product_info as execute

    return ProductInfoOutput.model_validate(
        await execute(get_current_token(), sku=sku, product_id=product_id)
    )


@mcp.tool()
async def get_product_full_info(sku: str | None = None, product_id: int | None = None) -> ProductInfoOutput:
    """Obtiene datos extendidos; requiere rol admin o colaborador."""
    from .tools import get_product_full_info as execute

    return ProductInfoOutput.model_validate(
        await execute(get_current_token(), sku=sku, product_id=product_id)
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


legacy_app = FastAPI(title="Growen MCP Products Server", version="1.0.0", lifespan=lifespan)


class InvokeRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


class InvokeResponse(BaseModel):
    tool_name: str
    result: Dict[str, Any]


@legacy_app.post("/invoke_tool", response_model=InvokeResponse, deprecated=True)
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
    authorization: str | None = Header(default=None),
):
    """Invoca una herramienta registrada en el servidor MCP.

    Requiere autenticación JWT vía header X-MCP-Token.
    
    Manejo de errores:
    - 401 si token ausente, inválido o expirado
    - 403 si permiso insuficiente (rol no autorizado)
    - 404 si tool desconocida
    - 429 si rate limit excedido
    - 400 para validaciones genéricas
    - 502 para errores de red hacia la API backend
    """
    global _legacy_invocations_total
    # Obtener token de cualquiera de los headers
    if os.getenv("MCP_LEGACY_RPC_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=410, detail="RPC MCP legacy deshabilitado")
    bearer = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    token_value = bearer or x_mcp_token or x_mcp_token_lower
    
    # Token requerido siempre (seguridad por defecto)
    if not token_value:
        raise HTTPException(status_code=401, detail="Token MCP requerido (header X-MCP-Token)")
    
    try:
        _legacy_invocations_total += 1
        logger.warning("Invocación RPC legacy recibida para tool=%s", payload.tool_name)
        result = await invoke_tool(payload.tool_name, payload.parameters, token_value)
        logger.debug("Tool %s ejecutada OK", payload.tool_name)
        return InvokeResponse(tool_name=payload.tool_name, result=result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MCPTokenExpired as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except MCPTokenInvalid as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except MCPUnauthorized as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except MCPRateLimited as e:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": str(e)},
            headers={"Retry-After": "60"},
        ) from e
    except MCPAuthError as e:
        # Catch-all para cualquier error de auth no manejado específicamente
        raise HTTPException(status_code=401, detail=str(e)) from e
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
        raise HTTPException(status_code=502, detail="Error upstream o interno") from e


@legacy_app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "mcp_products",
        "protocol": "mcp",
        "protocol_version": os.getenv("MCP_PROTOCOL_VERSION", "2025-11-25"),
        "endpoint": "/mcp",
        "legacy_invocations_total": _legacy_invocations_total,
    }

@legacy_app.get("/")
async def root():
    """Raíz simple para healthchecks legacy (Dockerfile usa "/").

    Nota: mantenemos también /health como endpoint canónico.
    """
    return {"status": "ok", "service": "mcp_products"}


legacy_app.mount("/mcp", mcp.streamable_http_app())
app = MCPBearerContextMiddleware(legacy_app)


# Para ejecución local: uvicorn mcp_servers.products_server.main:app --reload --port 8100

