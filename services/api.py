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
import warnings
from logging.handlers import RotatingFileHandler
import os
import time
from fastapi import FastAPI, Request, Depends
from fastapi import HTTPException as FastHTTPException
from pydantic import BaseModel  # Added for FrontError model (logging frontend errors)
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.exc import IntegrityError
import re

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
    backups_admin,
    sales,
)
from services.auth import require_csrf  # para override condicional en dev
from services.routers import bug_report  # router para reportes de bugs
from services.integrations.notion_errors import ErrorEvent, create_or_update_card  # type: ignore
from services.integrations.notion_client import load_notion_settings  # type: ignore
from services.integrations.notion_sections import upsert_report_as_child  # type: ignore

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

# Reducir ruido conocido: pypdf/cryptography ARC4 DeprecationWarning
try:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r".*ARC4 has been moved to cryptography\.hazmat\.decrepit\.ciphers\.algorithms.*",
        module=r"pypdf\._crypt_providers\._cryptography",
    )
except Exception:
    pass

# `redirect_slashes=False` evita redirecciones 307 entre `/ruta` y `/ruta/`,
# lo que rompe las solicitudes *preflight* de CORS.
app = FastAPI(title="Growen", redirect_slashes=False)
APP_IMPORT_TS = time.perf_counter()
APP_READY_TS: float | None = None
_STARTUP_METRIC_WRITTEN = False

# Diagnóstico: loguear DB URL efectiva al importar la app
try:
    from db.session import engine as _eng
    logger.info("DB effective URL: %s", str(_eng.url))
except Exception:
    pass


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra cada solicitud y captura excepciones con un correlation-id."""
    start = time.perf_counter()
    # Correlation / request id (prefer incoming header if present)
    try:
        corr = request.headers.get("x-correlation-id") or request.headers.get("x-request-id")
        if not corr:
            # generate lightweight id: epoch-ms + pid snippet
            corr = f"req-{int(time.time()*1000):x}-{os.getpid():x}"
    except Exception:
        corr = None
    try:
        resp = await call_next(request)
    except (FastHTTPException, StarletteHTTPException):
        # Deja que FastAPI maneje HTTPException (403/404/400, etc.)
        raise
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        if corr:
            logger.exception("EXC %s %s cid=%s (%.2fms)", request.method, request.url.path, corr, dur)
        else:
            logger.exception("EXC %s %s (%.2fms)", request.method, request.url.path, dur)
        # Notion: registrar tarjeta de error 500 si está habilitado (no bloquear respuesta)
        try:
            cfg = load_notion_settings()
            if cfg.enabled and cfg.errors_db:
                ev = ErrorEvent(
                    servicio="api",
                    entorno=os.getenv("ENV", "dev"),
                    url=str(request.url),
                    codigo="HTTP 500",
                    mensaje=f"Unhandled exception en {request.method} {request.url.path}",
                    stacktrace=None,  # el logger.exception dejó traza en archivo
                    correlation_id=corr,
                    etiquetas=["unhandled", "500"],
                    seccion=(
                        "Compras" if "/purchases" in request.url.path or "/compras" in request.url.path else
                        "Stock" if "/stock" in request.url.path or "/inventario" in request.url.path else
                        "App" if "/admin" in request.url.path else
                        None
                    ),
                )
                import asyncio
                if cfg.mode == "sections":
                    # En modo sections NO enviar reportes 500 a Notion desde middleware.
                    # Sólo dejamos el registro en logs para evitar ruido.
                    pass
                else:
                    asyncio.create_task(asyncio.to_thread(create_or_update_card, ev))
        except Exception:
            logger.debug("No se pudo encolar tarjeta Notion para 500", exc_info=True)
        # Devolver error con tono argento, breve y claro (sin faltar el respeto)
        return JSONResponse(
            {
                "detail": "Uy, algo se rompió de nuestro lado. Tranqui: ya lo estamos mirando. Si podés, probá de nuevo más tarde.",
            },
            status_code=500,
        )
    dur = (time.perf_counter() - start) * 1000
    if corr:
        # echo correlation id in response header so FE can surface it
        try:
            resp.headers["X-Correlation-Id"] = corr
        except Exception:
            pass
        logger.info("%s %s -> %s cid=%s (%.2fms)", request.method, request.url.path, resp.status_code, corr, dur)
    else:
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

# --- Exception Handlers Específicos ---
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):  # type: ignore[override]
    """Mapea errores de integridad conocidos a respuestas HTTP más útiles.

    - variants_sku_key -> 409 duplicate_sku
    - supplier_products (supplier_id, supplier_product_id) unique -> 409 duplicate_supplier_product
    Otros: 409 conflict genérico sin filtrar información sensible.
    """
    raw = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    # Detectar constraint por nombre o patrón
    detail = "conflict"
    code = "conflict"
    field = None
    status = 409
    if "variants_sku_key" in raw or re.search(r"duplicate key value.*variants", raw, re.I):
        code = "duplicate_sku"
        detail = "SKU ya existente"
        field = "sku"
    elif "supplier_products" in raw and ("duplicate key" in raw.lower()):
        code = "duplicate_supplier_product"
        detail = "Producto de proveedor ya registrado"
        field = "supplier_product_id"
    # Intentar rollback de la sesión (si existe) para limpiar estado
    try:  # best effort
        from sqlalchemy.ext.asyncio import AsyncSession
        sess = request.state.session if hasattr(request.state, "session") else None
        if isinstance(sess, AsyncSession):
            await sess.rollback()
    except Exception:
        pass
    payload = {"detail": detail, "code": code}
    if field:
        payload["field"] = field
    return JSONResponse(payload, status_code=status)

# Handler amistoso para errores de validación (422) sin cambiar el contrato
@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):  # type: ignore[override]
    """Registra detalles de validación por campo y devuelve el mismo formato por defecto.

    - No cambia la forma de la respuesta: {"detail": [...]}, status 422.
    - Loguea en español, con método y ruta, para diagnóstico más rápido.
    """
    try:
        # Extraer campos/loc y mensajes para el log
        errs = exc.errors()
        flat = []
        for e in errs:
            loc = ".".join([str(p) for p in e.get("loc", [])])
            msg = e.get("msg", "")
            typ = e.get("type", "")
            flat.append({"loc": loc, "msg": msg, "type": typ})
        logger.warning(
            "Validación fallida 422 %s %s: %s",
            request.method,
            request.url.path,
            flat,
        )
    except Exception:
        # Falla silenciosa del logger no debe afectar la respuesta
        pass
    # Mantener contrato por defecto de FastAPI
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

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
from services.routers import catalogs as catalogs_router  # import after logger setup
app.include_router(catalogs_router.router)
app.include_router(catalog.router)
app.include_router(imports.router)
app.include_router(canonical_products.canonical_router)
app.include_router(canonical_products.equivalences_router)
app.include_router(products_ex.router)
app.include_router(purchases.router)
app.include_router(sales.router)
app.include_router(media.router)
app.include_router(image_jobs.router)
app.include_router(images.router)
app.include_router(health.router)
app.include_router(services_admin.router)
app.include_router(backups_admin.router)
try:
    # include legacy /healthz for compatibility if present
    app.include_router(health.legacy_router)  # type: ignore[attr-defined]
except Exception:
    pass
app.include_router(debug.router, tags=["debug"])
app.include_router(bug_report.router)

# --- Router de diagnóstico frontend ---
from fastapi import APIRouter

frontend_diag_router = APIRouter(prefix="/debug/frontend", tags=["debug-frontend"])

@frontend_diag_router.get("/diag")
async def frontend_diag():
    """Reporte rápido del estado del build frontend.

    Devuelve:
      - build_present: bool si existe frontend/dist/index.html
      - assets_count: número de ficheros en frontend/dist/assets
      - main_bundle: nombre del bundle principal (heurística: el que incluye 'index-')
      - api_base_url: heurística de base URL que el cliente usaría
      - notes: recomendaciones si falta algo
    """
    root = Path(__file__).resolve().parents[1]
    fe_dist = root / "frontend" / "dist"
    index_html = fe_dist / "index.html"
    assets_dir = fe_dist / "assets"
    assets = []
    try:
        if assets_dir.exists():
            assets = [p.name for p in assets_dir.iterdir() if p.is_file()]
    except Exception:
        assets = []
    main_bundle = next((a for a in assets if a.startswith("index-") and a.endswith(".js")), None)
    build_present = index_html.exists() and bool(main_bundle)
    api_base = os.getenv("VITE_API_URL") or os.getenv("API_URL") or "http://127.0.0.1:8000"
    notes: list[str] = []
    if not build_present:
        notes.append("Falta build de producción (ejecutar npm run build en frontend/).")
    if not main_bundle:
        notes.append("No se detectó bundle principal index-*.js en /dist/assets.")
    if not assets:
        notes.append("Directorio assets vacío o inaccesible.")
    return {
        "build_present": build_present,
        "assets_count": len(assets),
        "main_bundle": main_bundle,
        "api_base_url": api_base,
        "notes": notes,
    }

@frontend_diag_router.get("/ping-auth")
async def frontend_ping_auth(request: Request):
    """Combina chequeo de build + estado de autenticación actual.

    Devuelve:
      - auth_request_ok: bool si /auth/me respondió
      - is_authenticated, role
      - cookies_present: lista de cookies relevantes detectadas en la request
      - correlation_hint: recuerda revisar cabecera X-Correlation-Id
    """
    # Re-usa lógica auth sin exponer internals
    from services.routers.auth import me  # import local para evitar ciclos
    try:
        auth_data = await me()  # type: ignore
        auth_ok = True
    except Exception:
        auth_data = {"error": "auth_me_failed"}
        auth_ok = False
    cookies_present = [c for c in ["growen_session", "csrf_token"] if c in request.cookies]
    return {
        "auth_request_ok": auth_ok,
        "auth": auth_data,
        "cookies_present": cookies_present,
        "correlation_hint": "Ver X-Correlation-Id en respuestas normales para trazas.",
    }

SENSITIVE_PREFIXES = {"SECRET", "OPENAI", "DB_PASS", "ADMIN_PASS", "API_KEY", "KEY", "TOKEN"}

def _is_safe_env_key(k: str) -> bool:
    uk = k.upper()
    return not any(p in uk for p in SENSITIVE_PREFIXES)

@frontend_diag_router.get("/env")
async def frontend_env():
    """Expone variables de entorno filtradas (no sensibles) para depuración frontend.

    No incluye claves que contengan prefijos potencialmente sensibles.
    """
    safe: dict[str, str] = {}
    for k, v in os.environ.items():
        if _is_safe_env_key(k) and len(v) < 500:
            safe[k] = v
    # Whitelist explícita de algunas sensibles pero truncadas podría añadirse más tarde.
    return {"env": safe, "count": len(safe)}

class FrontError(BaseModel):  # type: ignore
    """Modelo de error enviado por el ErrorBoundary.

    Hacemos casi todo opcional salvo message para ser tolerantes a versiones previas.
    """
    message: str
    stack: str | None = None
    component_stack: str | None = None
    user_agent: str | None = None
    # Campos extras potenciales en el futuro (ignorados si no llegan)

# --- Backup diario automático en arranque (idempotente por ventana de 24h) ---
try:
    from services.routers.backups_admin import ensure_daily_backup_on_boot
    _auto_meta = ensure_daily_backup_on_boot()
    logger.info("Backup auto on boot: %s", _auto_meta)
except Exception:
    logger.exception("Auto-backup check failed on boot")

@frontend_diag_router.post("/log-error")
async def frontend_log_error(payload: FrontError, request: Request):  # type: ignore
    """Persistir error capturado del frontend.

    Usa service_logs con action 'panic' y service 'frontend'.
    """
    try:
        from db.models import ServiceLog
        import socket
        sl = ServiceLog(
            service="frontend",
            correlation_id=f"fe-{int(time.time()*1000)}",
            action="panic",
            host=socket.gethostname(),
            pid=None,
            duration_ms=None,
            ok=False,
            level="ERROR",
            error=payload.message[:8000],
            hint=payload.component_stack,
            payload={
                "stack": (payload.stack or "")[:8000],
                "ua": payload.user_agent or request.headers.get("user-agent"),
                "path": request.headers.get("Referer"),
            },
        )
        # Persistimos si la DB está disponible; si falla seguimos (best-effort)
        async with SessionLocal() as s:  # type: ignore
            try:
                s.add(sl)
                await s.commit()
            except Exception:
                pass
    except Exception:
        pass
    return {"status": "ok"}

app.include_router(frontend_diag_router)

# Override CSRF en entorno de desarrollo para simplificar tests (no requiere cookie)
try:
    from agent_core.config import settings as _settings
    if _settings.env == "dev":
        app.dependency_overrides[require_csrf] = lambda: None
except Exception:
    pass

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

    # Periodic health logger (optional, controlled via SERVICE_HEALTH_LOG_SEC)
    try:
        import asyncio as _asyncio
        from db.models import ServiceLog as _ServiceLog
        import socket as _socket
        interval = int(os.getenv("SERVICE_HEALTH_LOG_SEC", "0") or "0")
        if interval > 0:
            async def _health_loop():
                from sqlalchemy import select as _select
                from services.routers.health import KNOWN_OPTIONAL_SERVICES as _SERVICES, health_service as _health_service
                while True:
                    try:
                        async with SessionLocal() as _s:  # type: ignore
                            for _name in _SERVICES:
                                try:
                                    h = await _health_service(_name)
                                    ok = bool(h.get("ok", False))
                                    level = "INFO" if ok else "ERROR"
                                    _s.add(_ServiceLog(service=_name, correlation_id=f"health-{int(time.time())}", action="health", host=_socket.gethostname(), pid=None, duration_ms=None, ok=ok, level=level, error=(None if ok else (h.get("detail") or "")), payload=h))
                                except Exception as _e:
                                    _s.add(_ServiceLog(service=_name, correlation_id=f"health-{int(time.time())}", action="health", host=_socket.gethostname(), pid=None, duration_ms=None, ok=False, level="ERROR", error=str(_e)))
                            await _s.commit()
                    except Exception:
                        pass
                    await _asyncio.sleep(max(10, interval))
            _asyncio.create_task(_health_loop())
    except Exception:
        pass


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
            resp = FileResponse(str(INDEX_HTML))
            # Evitar cache en index para que tome siempre el último bundle
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        # Soportar /app como alias legacy si el usuario ingresa esa ruta
        @app.get("/app", include_in_schema=False)
        async def spa_legacy_app():
            resp = FileResponse(str(INDEX_HTML))
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp

        # Catch-all for client-side routes. API/static/docs already matched above.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, full_path: str):
            # Explicitmente dejamos pasar 404 (estas rutas deberían matchear antes)
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
            resp = FileResponse(str(INDEX_HTML))
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp
except Exception:
    logger.exception("No se pudo montar el frontend estatico / SPA fallback")
