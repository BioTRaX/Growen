"""Aplicación FastAPI principal del agente."""

# --- Windows psycopg async fix: usar SelectorEventLoop ---
import sys, asyncio
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
# --- fin fix ---

import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from agent_core.config import settings
from ai.router import AIRouter
from .routers import (
    actions,
    chat,
    ws,
    catalog,
    imports,
    canonical_products,
    debug,
    auth,
    health,
)

level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("growen")
logging.getLogger("uvicorn").setLevel(level)
logging.getLogger("uvicorn.error").setLevel(level)
logging.getLogger("uvicorn.access").setLevel(level)

# `redirect_slashes=False` evita redirecciones 307 entre `/ruta` y `/ruta/`,
# lo que rompe las solicitudes *preflight* de CORS.
app = FastAPI(title="Growen", redirect_slashes=False)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra cada solicitud y captura excepciones."""
    start = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        logger.exception("EXC %s %s (%.2fms)", request.method, request.url.path, dur)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    dur = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.2fms)", request.method, request.url.path, resp.status_code, dur)
    return resp

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(actions.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(imports.router)
app.include_router(canonical_products.canonical_router)
app.include_router(canonical_products.equivalences_router)
app.include_router(health.router)
app.include_router(debug.router, tags=["debug"])


@app.get("/health")
async def health() -> dict[str, str]:
    """Devuelve OK si la aplicación está viva."""
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai() -> dict[str, list[str]]:
    """Informa los proveedores disponibles de IA."""
    router = AIRouter(settings)
    return {"providers": router.available_providers()}
