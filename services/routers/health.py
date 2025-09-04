# NG-HEADER: Nombre de archivo: health.py
# NG-HEADER: Ubicación: services/routers/health.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List
import shutil

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings
from ai.router import AIRouter
from db.session import get_db


router = APIRouter(prefix="/health", tags=["health"])
START_TIME = time.monotonic()


def _status(ok: bool, detail: str | None = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": ok}
    if detail:
        out["detail"] = detail
    return out


@router.get("")
async def health_root() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/ai")
async def health_ai() -> Dict[str, List[str]]:
    router = AIRouter(settings)
    return {"providers": router.available_providers()}


@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    await db.execute(text("SELECT 1"))
    return _status(True)


@router.get("/redis")
async def health_redis() -> Dict[str, Any]:
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
    """Verifica broker Redis, tamaño de cola 'images' y presencia de workers."""
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        return _status(False, detail="skipped: RUN_INLINE_JOBS=1")
    try:
        import redis  # type: ignore

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, decode_responses=True)  # type: ignore[attr-defined]
        broker_ok = bool(client.ping())
        prefix = os.getenv("DRAMATIQ_REDIS_PREFIX", "dramatiq")
        q_images = f"{prefix}:queue:images"
        q_exists = bool(client.exists(q_images))
        q_len = int(client.llen(q_images)) if q_exists else 0
        # Buscar workers registrados (heurística)
        worker_keys = list(client.scan_iter(f"{prefix}:worker*"))
        workers_count = len(worker_keys)
        return {
            "ok": broker_ok and (workers_count >= 1),
            "broker_ok": broker_ok,
            "queues": {"images": {"exists": q_exists, "size": q_len}},
            "workers": {"count": workers_count, "keys": worker_keys[:10]},
        }
    except Exception as e:
        return _status(False, detail=str(e))


@router.get("/summary")
async def health_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
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
            q_images = f"{prefix}:queue:images"
            q_exists = bool(client.exists(q_images))
            q_len = int(client.llen(q_images)) if q_exists else 0
            worker_keys = list(client.scan_iter(f"{prefix}:worker*"))
            workers_count = len(worker_keys)
            dramatiq_details = {
                "ok": broker_ok and (workers_count >= 1),
                "broker_ok": broker_ok,
                "queues": {"images": {"exists": q_exists, "size": q_len}},
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
    }
    overall_ok = db_ok and redis_ok and storage_ok
    return {"status": "ok" if overall_ok else "degraded", "details": details}


# Legacy compatibility: keep /healthz/db
legacy_router = APIRouter(prefix="/healthz", tags=["health"], include_in_schema=False)


@legacy_router.get("/db")
async def legacy_health_db(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}
