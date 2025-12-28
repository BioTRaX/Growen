# NG-HEADER: Nombre de archivo: health.py
# NG-HEADER: Ubicación: services/routers/health.py
# NG-HEADER: Descripción: Endpoints de healthcheck y estado de servicios.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

"""Endpoints de health y diagnostico del sistema.

Incluye verificaciones de:
- Liveness básico (`/health`)
- Dependencias por servicio opcional (`/health/service/{name}`)
- Conectividad DB/Redis/Storage (`/health/db`, `/health/redis`, `/health/storage`)
- Resumen general (`/health/summary`)
- Compatibilidad legacy (`/healthz/db`)
"""

import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import shutil
import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings
from ai.router import AIRouter
from db.session import get_db


router = APIRouter(prefix="/health", tags=["health"])
START_TIME = time.monotonic()
KNOWN_OPTIONAL_SERVICES = [
    "pdf_import",
    "playwright",
    "image_processing",
    "dramatiq",
]


def _status(ok: bool, detail: str | None = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": ok}
    if detail:
        out["detail"] = detail
    return out


@router.get("")
async def health_root() -> Dict[str, str]:
    """Liveness simple del backend (si responde, está vivo)."""
    return {"status": "ok"}


def _which_any(names: List[str]) -> Tuple[str | None, str]:
    for n in names:
        p = shutil.which(n)
        if p:
            return p, n
    return None, names[0]


def _which_with_fallback(name: str, fallback_patterns: List[str] | None = None) -> str | None:
    """Busca un ejecutable en PATH y, si no lo encuentra, en rutas de fallback de Windows.
    
    Args:
        name: Nombre del ejecutable (ej: "qpdf", "tesseract")
        fallback_patterns: Lista de patrones glob para buscar en Windows
                          (ej: [r"C:\\Program Files\\qpdf*\\bin\\qpdf.exe"])
    
    Returns:
        Ruta al ejecutable si se encuentra, None si no.
    """
    # Primero buscar en PATH
    found = shutil.which(name)
    if found:
        return found
    
    # Si no hay fallbacks o no estamos en Windows, retornar None
    if not fallback_patterns or os.name != "nt":
        return None
    
    # Buscar en rutas de fallback usando glob
    import glob
    for pattern in fallback_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isfile(match) and os.access(match, os.X_OK):
                return match
    
    return None


# Rutas de fallback comunes para Windows
WINDOWS_FALLBACK_PATHS = {
    "qpdf": [
        r"C:\Program Files\qpdf*\bin\qpdf.exe",
        r"C:\Program Files (x86)\qpdf*\bin\qpdf.exe",
    ],
    "tesseract": [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ],
    "ghostscript": [
        r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs*\bin\gswin32c.exe",
        r"C:\Program Files (x86)\gs\gs*\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
    ],
}


@router.get("/service/{name}")
async def health_service(name: str) -> Dict[str, Any]:
    """Chequeos específicos por servicio opcional (pdf_import, playwright, etc.)."""
    name = name.lower()
    if name == "pdf_import":
        # Check Python deps + system tools
        def _try(name: str) -> bool:
            try:
                __import__(name)
                return True
            except Exception:
                return False
        ocrmypdf_ok = _try("ocrmypdf")
        pdfplumber_ok = _try("pdfplumber")
        camelot_ok = _try("camelot")
        
        # Usar fallbacks de Windows para herramientas del sistema
        tesseract_path = _which_with_fallback("tesseract", WINDOWS_FALLBACK_PATHS.get("tesseract"))
        qpdf_path = _which_with_fallback("qpdf", WINDOWS_FALLBACK_PATHS.get("qpdf"))
        gs_path = _which_with_fallback("gswin64c", WINDOWS_FALLBACK_PATHS.get("ghostscript"))
        if not gs_path:
            gs_path = _which_with_fallback("gswin32c")
        if not gs_path:
            gs_path = _which_with_fallback("gs")
        
        hints: List[str] = []
        if not tesseract_path:
            hints.append("Instalá Tesseract (con idioma español)")
        if not qpdf_path:
            hints.append("Instalá QPDF")
        if not gs_path:
            hints.append("Instalá Ghostscript")
        if not ocrmypdf_ok:
            hints.append("Instalá ocrmypdf en el venv")
        ok = ocrmypdf_ok and bool(tesseract_path and qpdf_path and gs_path)
        return {"service": name, "ok": ok, "deps": {"ocrmypdf": ocrmypdf_ok, "pdfplumber": pdfplumber_ok, "camelot": camelot_ok, "tesseract": bool(tesseract_path), "tesseract_path": tesseract_path, "qpdf": bool(qpdf_path), "qpdf_path": qpdf_path, "ghostscript": bool(gs_path), "gs_path": gs_path}, "hints": hints}
    if name == "playwright":
        try:
            import importlib
            importlib.import_module("playwright")
            # quick version check via subprocess, doesn't download
            try:
                r = subprocess.run(["python", "-m", "playwright", "--version"], capture_output=True, text=True, timeout=5)
                ver = (r.stdout or r.stderr).strip()
            except Exception:
                ver = ""
            return {"service": name, "ok": True, "version": ver, "hints": ["Si falta Chromium: python -m playwright install chromium"]}
        except Exception as e:
            return {"service": name, "ok": False, "error": str(e), "hints": ["pip install playwright", "python -m playwright install chromium"]}
    if name == "image_processing":
        def _try(name: str) -> bool:
            try:
                __import__(name)
                return True
            except Exception:
                return False
        pillow_ok = _try("PIL") or _try("Pillow")
        rembg_ok = _try("rembg")
        cv_ok = _try("cv2")
        ok = pillow_ok
        hints: List[str] = []
        if not pillow_ok:
            hints.append("pip install Pillow")
        if not rembg_ok:
            hints.append("pip install rembg")
        return {"service": name, "ok": ok, "deps": {"pillow": pillow_ok, "rembg": rembg_ok, "opencv": cv_ok}, "hints": hints}
    if name == "dramatiq":
        return await health_dramatiq()
    return {"service": name, "ok": False, "detail": "servicio desconocido"}


@router.get("/ai")
async def health_ai() -> Dict[str, List[str]]:
    """Lista proveedores de AI disponibles según configuración actual."""
    router = AIRouter(settings)
    return {"providers": router.available_providers()}


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Valida conexión a la base de datos (SELECT 1)."""
    await db.execute(text("SELECT 1"))
    return _status(True)


@router.get("/redis")
async def health_redis() -> Dict[str, Any]:
    """Verifica conexión a Redis; en RUN_INLINE_JOBS=1 se omite.

    Devuelve `ok` y opcional `detail` con error o motivo de omisión.
    """
    # In inline mode we intentionally don't require Redis
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        return _status(False, detail="skipped: RUN_INLINE_JOBS=1")
    try:
        import redis  # type: ignore

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, decode_responses=True)  # type: ignore[attr-defined]
        pong = client.ping()
        return _status(bool(pong))
    except Exception as e:  # pragma: no cover - best effort
        return _status(False, detail=str(e))


@router.get("/storage")
async def health_storage() -> Dict[str, Any]:
    """Prueba escritura/lectura en carpeta de media y reporta espacio libre."""
    try:
        root = Path(__file__).resolve().parents[2]
        media_root = Path(os.getenv("MEDIA_ROOT", str(root / "Devs" / "Imagenes")))
        media_root.mkdir(parents=True, exist_ok=True)
        test_file = media_root / ".healthcheck.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        total, used, free = shutil.disk_usage(str(media_root))
        return {"ok": True, "free_bytes": int(free), "total_bytes": int(total)}
    except Exception as e:
        return _status(False, detail=str(e))


@router.get("/optional")
async def health_optional() -> Dict[str, Any]:
    """Presencia de dependencias opcionales de Python (best-effort)."""
    def _try_import(name: str) -> bool:
        try:
            __import__(name)
            return True
        except Exception:
            return False

    checks = {
        "tenacity": _try_import("tenacity"),
        "playwright": _try_import("playwright"),
        "pdfplumber": _try_import("pdfplumber"),
        "camelot": _try_import("camelot"),
        "ocrmypdf": _try_import("ocrmypdf"),
        "pdf2image": _try_import("pdf2image"),
        "pytesseract": _try_import("pytesseract"),
        "opencv": _try_import("cv2"),
    }
    return checks


@router.get("/dramatiq")
async def health_dramatiq() -> Dict[str, Any]:
    """Verifica broker Redis, tamaño de colas y presencia de workers."""
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        return _status(False, detail="skipped: RUN_INLINE_JOBS=1")
    try:
        import redis  # type: ignore

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, decode_responses=True)  # type: ignore[attr-defined]
        broker_ok = bool(client.ping())
        prefix = os.getenv("DRAMATIQ_REDIS_PREFIX", "dramatiq")
        
        # Verificar múltiples colas
        queues_info = {}
        for queue_name in ["images", "market", "drive_sync", "catalog"]:
            q_name = f"{prefix}:queue:{queue_name}"
            q_exists = bool(client.exists(q_name))
            q_len = int(client.llen(q_name)) if q_exists else 0
            queues_info[queue_name] = {"exists": q_exists, "size": q_len}
        
        # Buscar workers registrados (heurística)
        worker_keys = list(client.scan_iter(f"{prefix}:worker*"))
        workers_count = len(worker_keys)
        
        # Verificar que haya al menos un worker activo
        has_workers = workers_count >= 1
        
        return {
            "ok": broker_ok and has_workers,
            "broker_ok": broker_ok,
            "queues": queues_info,
            "workers": {"count": workers_count, "keys": worker_keys[:10]},
        }
    except Exception as e:
        return _status(False, detail=str(e))


@router.get("/summary")
async def health_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Resumen general de salud del sistema.

    Incluye DB, Redis, Storage, Dramatiq, proveedores de AI, assets frontend,
    migraciones y servicios opcionales.
    """
    # DB
    db_ok = True
    db_detail = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_detail = str(e)

    # Redis
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        redis_ok = False
        redis_detail = "skipped: RUN_INLINE_JOBS=1"
    else:
        try:
            import redis  # type: ignore

            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(url, decode_responses=True)  # type: ignore[attr-defined]
            redis_ok = bool(client.ping())
            redis_detail = None
        except Exception as e:
            redis_ok = False
            redis_detail = str(e)

    # Storage
    try:
        root = Path(__file__).resolve().parents[2]
        media_root = Path(os.getenv("MEDIA_ROOT", str(root / "Devs" / "Imagenes")))
        media_root.mkdir(parents=True, exist_ok=True)
        test_file = media_root / ".healthcheck.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        total, used, free = shutil.disk_usage(str(media_root))
        storage_ok = True
        storage_detail = None
    except Exception as e:
        storage_ok = False
        storage_detail = str(e)

    # Dramatiq
    dramatiq_details: Dict[str, Any]
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        dramatiq_details = _status(False, detail="skipped: RUN_INLINE_JOBS=1")
    else:
        try:
            import redis  # type: ignore

            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(url, decode_responses=True)  # type: ignore[attr-defined]
            broker_ok = bool(client.ping())
            prefix = os.getenv("DRAMATIQ_REDIS_PREFIX", "dramatiq")
            
            # Verificar múltiples colas
            queues_info = {}
            for queue_name in ["images", "market", "drive_sync", "catalog"]:
                q_name = f"{prefix}:queue:{queue_name}"
                q_exists = bool(client.exists(q_name))
                q_len = int(client.llen(q_name)) if q_exists else 0
                queues_info[queue_name] = {"exists": q_exists, "size": q_len}
            
            worker_keys = list(client.scan_iter(f"{prefix}:worker*"))
            workers_count = len(worker_keys)
            dramatiq_details = {
                "ok": broker_ok and (workers_count >= 1),
                "broker_ok": broker_ok,
                "queues": queues_info,
                "workers": {"count": workers_count, "keys": worker_keys[:10]},
            }
        except Exception as e:
            dramatiq_details = _status(False, detail=str(e))

    # AI providers
    ai_providers: List[str] = []
    try:
        ai_providers = AIRouter(settings).available_providers()
    except Exception:
        ai_providers = []

    # DB migration info (best-effort)
    migration = {"current_revision": None, "scripts": 0}
    try:
        # current revision
        res = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = res.first()
        if row:
            migration["current_revision"] = row[0]
    except Exception:
        pass
    try:
        mig_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
        if mig_dir.exists():
            migration["scripts"] = len([p for p in mig_dir.rglob("*.py") if p.is_file()])
    except Exception:
        pass

    # Frontend built assets
    fe_dist_ok = False
    try:
        fe_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "assets"
        fe_dist_ok = fe_dir.exists() and any(fe_dir.iterdir())
    except Exception:
        fe_dist_ok = False

    # Optional deps
    def _try_import(name: str) -> bool:
        try:
            __import__(name)
            return True
        except Exception:
            return False

    optional = {
        "tenacity": _try_import("tenacity"),
        "playwright": _try_import("playwright"),
        "pdfplumber": _try_import("pdfplumber"),
        "camelot": _try_import("camelot"),
        "ocrmypdf": _try_import("ocrmypdf"),
        "pdf2image": _try_import("pdf2image"),
        "pytesseract": _try_import("pytesseract"),
        "opencv": _try_import("cv2"),
    }

    # Process info
    uptime_seconds = int(max(0.0, time.monotonic() - START_TIME))
    host = socket.gethostname()

    # Per optional-service health (best-effort)
    per_services: Dict[str, Any] = {}
    try:
        for name in KNOWN_OPTIONAL_SERVICES:
            try:
                per_services[name] = await health_service(name)
            except Exception as e:
                per_services[name] = _status(False, detail=str(e))
    except Exception:
        per_services = {}

    details: Dict[str, Any] = {
        "db": _status(db_ok, db_detail),
        "redis": _status(redis_ok, redis_detail),
        "storage": ({"ok": storage_ok, "detail": storage_detail, "free_bytes": int(free) if storage_ok else None} if storage_ok else _status(False, storage_detail)),
        "dramatiq": dramatiq_details,
        "ai_providers": ai_providers,
        "optional": optional,
        "frontend_built": fe_dist_ok,
        "db_migration": migration,
        "process": {"uptime_seconds": uptime_seconds, "host": host},
        "services": per_services,
    }
    overall_ok = db_ok and redis_ok and storage_ok
    return {"status": "ok" if overall_ok else "degraded", "details": details}


# Legacy compatibility: keep /healthz/db
legacy_router = APIRouter(prefix="/healthz", tags=["health"], include_in_schema=False)


@legacy_router.get("/db")
async def legacy_health_db(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Compatibilidad legacy para probes que consultan /healthz/db."""
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
