# NG-HEADER: Nombre de archivo: api.py
# NG-HEADER: Ubicación: services/api.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Aplicación FastAPI principal del agente."""

# --- Windows psycopg async fix (no-op en otros SO) ---
import sys, asyncio
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
# --- end fix ---

import logging
from logging.handlers import RotatingFileHandler
import os
import time
from fastapi import FastAPI, Request
from fastapi import HTTPException as FastHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse, FileResponse

from agent_core.config import settings
from db.session import engine, SessionLocal
from db.base import Base
import db.models  # ensure models are imported so metadata has all tables
from ai.router import AIRouter
from .routers import (
    actions,
    chat,
    ws,
    catalog,
    imports,
    canonical_products,
    products_ex,
    purchases,
    media,
    image_jobs,
    images,
    debug,
    auth,
    health,
    services_admin,
)

raw_level = os.getenv("LOG_LEVEL", "INFO") or "INFO"
level_name = raw_level.strip().upper()
if level_name not in logging._nameToLevel:
    level_name = "INFO"
logger = logging.getLogger("growen")
logger.setLevel(level_name)
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(fmt)

file_handler = None
log_path = LOG_DIR / "backend.log"
try:
    # Probar permiso de append de manera proactiva para evitar 'Logging error' en Windows
    with open(log_path, "a", encoding="utf-8"):
        pass
    # delay=True evita abrir el archivo hasta el primer log; reduce errores de locking en Windows
    file_handler = RotatingFileHandler(
        str(log_path), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=True
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
except Exception:
    # Sin permisos o archivo bloqueado: continuar solo con consola
    file_handler = None

logger.addHandler(stream_handler)

handlers = [h for h in (file_handler, stream_handler) if h is not None]
logging.getLogger("uvicorn").handlers = handlers
logging.getLogger("uvicorn.error").handlers = handlers
logging.getLogger("uvicorn.access").handlers = handlers
logging.getLogger("uvicorn").setLevel(level_name)
logging.getLogger("uvicorn.error").setLevel(level_name)
logging.getLogger("uvicorn.access").setLevel(level_name)

# `redirect_slashes=False` evita redirecciones 307 entre `/ruta` y `/ruta/`,
# lo que rompe las solicitudes *preflight* de CORS.
app = FastAPI(title="Growen", redirect_slashes=False)
APP_IMPORT_TS = time.perf_counter()
APP_READY_TS: float | None = None
_STARTUP_METRIC_WRITTEN = False


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra cada solicitud y captura excepciones."""
    start = time.perf_counter()
    try:
        resp = await call_next(request)
    except (FastHTTPException, StarletteHTTPException):
        # Deja que FastAPI maneje HTTPException (403/404/400, etc.)
        raise
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        logger.exception("EXC %s %s (%.2fms)", request.method, request.url.path, dur)
        # Devolver error con tono argento, breve y claro (sin faltar el respeto)
        return JSONResponse(
            {
                "detail": "Uy, algo se rompió de nuestro lado. Tranqui: ya lo estamos mirando. Si podés, probá de nuevo más tarde.",
            },
            status_code=500,
        )
    dur = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.2fms)", request.method, request.url.path, resp.status_code, dur)
    # Record startup metric once on first successful request
    global _STARTUP_METRIC_WRITTEN
    if not _STARTUP_METRIC_WRITTEN:
        try:
            from db.models import StartupMetric  # local import to avoid early import
            ttfb_ms = int((time.perf_counter() - APP_IMPORT_TS) * 1000)
            app_ready_ms = int(((APP_READY_TS or APP_IMPORT_TS) - APP_IMPORT_TS) * 1000)
            async with SessionLocal() as s:  # type: ignore
                s.add(StartupMetric(ttfb_ms=ttfb_ms, app_ready_ms=app_ready_ms, meta={"path": request.url.path}))
                await s.commit()
            _STARTUP_METRIC_WRITTEN = True
        except Exception:
            pass
    return resp

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Doctor on boot (optional)
if os.getenv("RUN_DOCTOR_ON_BOOT", "1") == "1":
    try:
        from tools.doctor import run_doctor

        fail = os.getenv("DOCTOR_FAIL_ON_ERROR", "1") == "1"
        code = run_doctor(fail_on_error=fail)
        if code != 0 and fail:
            # Fail fast in production contexts
            logger.critical("Doctor failed on boot, exiting.")
            raise SystemExit("Doctor failed on boot")
    except SystemExit:
        raise
    except Exception:
        logger.exception("Doctor check failed")
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(actions.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(imports.router)
app.include_router(canonical_products.canonical_router)
app.include_router(canonical_products.equivalences_router)
app.include_router(products_ex.router)
app.include_router(purchases.router)
app.include_router(media.router)
app.include_router(image_jobs.router)
app.include_router(images.router)
app.include_router(health.router)
app.include_router(services_admin.router)
try:
    # include legacy /healthz for compatibility if present
    app.include_router(health.legacy_router)  # type: ignore[attr-defined]
except Exception:
    pass
app.include_router(debug.router, tags=["debug"])

@app.on_event("startup")
async def _init_inmemory_db():
    """Auto-crea el esquema cuando usamos SQLite en memoria (tests)."""
    try:
        url = str(engine.url)
        if url.startswith("sqlite+") and (":memory:" in url or "mode=memory" in url):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    except Exception:
        logger.exception("No se pudo inicializar el esquema en memoria")
    # Auto-start optional services flagged as auto_start (best-effort, non-blocking)
    try:
        from db.models import Service
        from sqlalchemy import select
        from services.orchestrator import start_service as _svc_start
        async with SessionLocal() as s:  # type: ignore
            rows = (await s.execute(select(Service).where(Service.auto_start == True))).scalars().all()
            for r in rows:
                try:
                    _svc_start(r.name, correlation_id=f"boot-{int(time.time())}")
                except Exception:
                    pass
    except Exception:
        pass

    # Mark app ready timestamp
    global APP_READY_TS
    try:
        APP_READY_TS = time.perf_counter()
    except Exception:
        APP_READY_TS = None


# Unificado en services.routers.health

# --- Static frontend (built) + SPA fallback ---
try:
    ROOT = Path(__file__).resolve().parents[1]
    FE_DIST = ROOT / "frontend" / "dist"
    INDEX_HTML = FE_DIST / "index.html"
    ASSETS_DIR = FE_DIST / "assets"

    if ASSETS_DIR.exists():
        # Serve bundled assets (JS/CSS/images) from /assets
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    # Static media (user/product images, attachments)
    MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(ROOT / "Devs" / "Imagenes")))
    try:
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception:
        logger.exception("No se pudo crear el directorio MEDIA_ROOT: %s", MEDIA_ROOT)
    if MEDIA_ROOT.exists():
        app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

    # Serve favicon if present to avoid catching it with SPA fallback
    FAVICON = FE_DIST / "favicon.ico"
    if FAVICON.exists():
        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            return FileResponse(str(FAVICON))

    # Root path -> index.html y catch-all SPA
    if INDEX_HTML.exists():
        @app.get("/", include_in_schema=False)
        async def spa_root():
            return FileResponse(str(INDEX_HTML))

        # Catch-all for client-side routes. API/static/docs already matched above.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, full_path: str):
            # Explicitly let these go 404 here (they should be matched by their own routes first)
            blocked = (
                full_path.startswith("assets")
                or full_path.startswith("media")
                or full_path.startswith("api")
                or full_path.startswith("docs")
                or full_path.startswith("redoc")
                or full_path.startswith("openapi")
            )
            if blocked or not INDEX_HTML.exists():
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return FileResponse(str(INDEX_HTML))
except Exception:
    logger.exception("No se pudo montar el frontend estatico / SPA fallback")
