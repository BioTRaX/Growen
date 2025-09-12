# NG-HEADER: Nombre de archivo: image_jobs.py
# NG-HEADER: Ubicación: services/routers/image_jobs.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse
import asyncio
from fastapi.responses import FileResponse
import mimetypes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, exists
from pydantic import BaseModel

from db.models import ImageJob, ImageJobLog
from db.session import get_session
from services.auth import require_roles, require_csrf


router = APIRouter(prefix="/admin/image-jobs", tags=["images"])
logger = logging.getLogger(__name__)


class JobSettings(BaseModel):
    active: bool
    mode: str
    window_start: Optional[str] = None  # HH:MM
    window_end: Optional[str] = None
    retries: int
    rate_rps: float
    burst: int
    log_retention_days: int
    purge_ttl_days: int


@router.get("/status", dependencies=[Depends(require_roles("admin"))])
async def status(db: AsyncSession = Depends(get_session)):
    job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
    if not job:
        job = ImageJob(name="imagenes_productos", active=False, mode="off")
        db.add(job)
        await db.commit()
        await db.refresh(job)
    # Heurstica: running si hubo logs en el altimo minuto
    from datetime import datetime, timedelta
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    last_logs_q = select(ImageJobLog).where(ImageJobLog.job_name == job.name).order_by(ImageJobLog.created_at.desc()).limit(25)
    last_logs_res = await db.execute(last_logs_q)
    last_logs = last_logs_res.scalars().all()
    running = any(getattr(l, "created_at", one_min_ago) >= one_min_ago for l in last_logs)

    # Pending: productos con stock>0 sin imagen activa
    from db.models import Product, Image
    subq_has_img = select(Image.id).where(Image.product_id == Product.id, Image.active == True).exists()
    pending = (await db.execute(select(func.count()).select_from(Product).where(Product.stock > 0).where(~subq_has_img))).scalar() or 0
    # Total candidatos (stock>0)
    total_candidates = (await db.execute(select(func.count()).select_from(Product).where(Product.stock > 0))).scalar() or 0

    # Current product: por altimo log con data.product_id
    current_product = None
    for l in last_logs:
        try:
            if l.data and isinstance(l.data, dict) and l.data.get("product_id"):
                current_product = {"product_id": l.data.get("product_id"), "title": l.data.get("title"), "stage": l.message}
                break
        except Exception:
            pass
    logs = [
        {"level": l.level, "message": l.message, "created_at": (l.created_at.isoformat() if getattr(l, "created_at", None) else None), "data": (l.data or {})}
        for l in last_logs
    ]
    # Basic success/failure counters (últimas 24h)
    day_ago = datetime.utcnow() - timedelta(hours=24)
    recent = (await db.execute(select(ImageJobLog).where(ImageJobLog.created_at >= day_ago))).scalars().all()
    ok = sum(1 for r in recent if r.message in ("done", "downloaded") and (r.level or "INFO") in ("INFO", "SUCCESS"))
    fail = sum(1 for r in recent if (r.level or "").upper() == "ERROR")
    processed = (total_candidates - pending) if total_candidates >= pending else ok + fail
    total_for_progress = total_candidates if total_candidates > 0 else (processed + pending)
    percent = int(round((processed / total_for_progress) * 100)) if total_for_progress else 0
    return {
        "name": job.name,
        "active": job.active,
        "mode": job.mode,
        "running": running,
        "pending": pending,
        "ok": ok,
        "fail": fail,
        "current_product": current_product,
        "logs": logs,
        "progress": {
            "total": total_candidates,
            "pending": pending,
            "processed": processed,
            "percent": percent,
        },
    }


@router.post("/probe", dependencies=[Depends(require_roles("admin"))])
async def probe(title: str, db: AsyncSession = Depends(get_session)):
    """Busca candidatos por título en Santa Planta y devuelve URLs e imagen detectada.

    No guarda nada; sirve para probar desde el panel.
    """
    from services.scrapers.santaplanta import search_by_title, extract_product_image
    try:
        if not (title or "").strip():
            raise HTTPException(status_code=400, detail="title requerido")
        urls = await search_by_title(title)
        first_img = None
        for u in urls:
            try:
                first_img = await extract_product_image(u)
            except Exception:
                first_img = None
            if first_img:
                break
        # Log liviano para trazabilidad
        db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="probe", data={"title": title, "urls": urls[:3], "image": first_img}))
        await db.commit()
        return {"ok": True, "urls": urls, "image": first_img}
    except HTTPException:
        raise
    except Exception as e:
        # No romper el panel; devolver detalle y registrar
        try:
            db.add(ImageJobLog(job_name="imagenes_productos", level="ERROR", message="probe_error", data={"title": title, "error": str(e)[:200]}))
            await db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"probe_failed: {e}")


@router.put("/settings", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def put_settings(payload: JobSettings, db: AsyncSession = Depends(get_session)):
    job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
    if not job:
        job = ImageJob(name="imagenes_productos")
        db.add(job)
        await db.flush()
    job.active = payload.active
    if payload.mode not in ("off", "on", "window"):
        raise HTTPException(status_code=400, detail="Modo invalido")
    job.mode = payload.mode
    # times are HH:MM; for simplicity store as None for now
    job.retries = payload.retries
    job.rate_rps = payload.rate_rps
    job.burst = payload.burst
    job.log_retention_days = payload.log_retention_days
    job.purge_ttl_days = payload.purge_ttl_days
    await db.commit()
    return {"status": "ok"}


@router.get("/logs", dependencies=[Depends(require_roles("admin"))])
async def list_logs(page: int = 1, page_size: int = 50, q: str | None = Query(None), db: AsyncSession = Depends(get_session)):
    if page_size > 200:
        page_size = 200
    stmt = select(ImageJobLog).order_by(ImageJobLog.created_at.desc())
    if q:
        # naive filter on message contains
        from sqlalchemy import or_
        stmt = stmt.where(ImageJobLog.message.ilike(f"%{q}%"))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    items = [f"[{r.level}] {r.created_at.isoformat()} - {r.message}" for r in rows]
    return {"items": items, "count": len(items)}


@router.get("/logs.ndjson", dependencies=[Depends(require_roles("admin"))])
async def logs_ndjson(limit: int = 200, correlation_id: str | None = Query(None), db: AsyncSession = Depends(get_session)):
    from fastapi.responses import PlainTextResponse
    stmt = select(ImageJobLog).order_by(ImageJobLog.created_at.desc()).limit(limit)
    if correlation_id:
        from sqlalchemy import cast, String
        # filter by data.correlation_id JSON field where supported; fallback to LIKE on serialized JSON
        try:
            from sqlalchemy import text
            # For engines with JSON support this may be adapted; we keep simple selection then filter in Python
            rows = (await db.execute(stmt)).scalars().all()
        except Exception:
            rows = (await db.execute(stmt)).scalars().all()
    else:
        rows = (await db.execute(stmt)).scalars().all()
    lines = []
    import json
    for r in rows[::-1]:  # oldest first
        obj = {
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            "level": r.level,
            "message": r.message,
            "data": r.data or {},
        }
        if correlation_id and obj["data"].get("correlation_id") != correlation_id:
            continue
        lines.append(json.dumps(obj, ensure_ascii=False))
    return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")


@router.get("/ndjson-file", dependencies=[Depends(require_roles("admin"))])
async def ndjson_file(limit: int = 200):
    """Return the tail of the crawler NDJSON log file written by ctx_logger."""
    from pathlib import Path
    p = Path("logs") / "image_crawler.ndjson"
    if not p.exists():
        return PlainTextResponse("", media_type="application/x-ndjson")
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
        return PlainTextResponse("\n".join(lines), media_type="application/x-ndjson")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read ndjson file: {e}")


@router.post("/clean-logs", dependencies=[Depends(require_roles("admin"))])
async def clean_logs_endpoint():
    """Clean crawler logs and snapshots (calls ctx_logger.clean_logs)."""
    try:
        from services.logging.ctx_logger import clean_logs

        clean_logs()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not clean logs: {e}")


@router.get("/snapshots", dependencies=[Depends(require_roles("admin"))])
async def list_snapshots(correlation_id: str):
    from pathlib import Path
    base = Path("tmp") / "crawl" / correlation_id
    if not base.exists() or not base.is_dir():
        return {"snapshots": []}
    out = []
    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue
        out.append({"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime})
    return {"snapshots": out}


@router.get("/snapshots/file", dependencies=[Depends(require_roles("admin"))])
async def get_snapshot_file(path: str):
    # path is a relative file name within tmp/crawl/<cid>
    from pathlib import Path
    base = Path("tmp") / "crawl"
    try:
        p = (base / path).resolve()
        if not str(p).startswith(str(base.resolve())):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        ctype, _ = mimetypes.guess_type(str(p))
        if ctype is None:
            ctype = "application/octet-stream"
        return FileResponse(str(p), media_type=ctype, filename=p.name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not serve file: {e}")


# --- Triggers ---
import os
from services.jobs.images import crawl_catalog_missing_images, purge_soft_deleted


@router.post("/trigger/crawl-missing", dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))])
async def trigger_crawl_missing(scope: str = Query("stock"), db: AsyncSession = Depends(get_session)):
    # Dev fallback: run inline if requested (no Redis needed)
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        try:
            # Run in a separate thread so images actor can call asyncio.run safely
            import anyio
            await anyio.to_thread.run_sync(lambda: crawl_catalog_missing_images.fn(scope))  # type: ignore[attr-defined]
            return {"status": "ran-inline", "scope": scope}
        except Exception as e:
            logger.exception("Fallo inline crawl-missing")
            raise HTTPException(status_code=500, detail=f"Fallo inline: {e}")
    try:
        if scope not in ("stock", "all"):
            raise HTTPException(status_code=400, detail="scope inválido")
        crawl_catalog_missing_images.send(scope)
    except Exception as e:
        logger.exception("No se pudo encolar crawl-missing")
        raise HTTPException(status_code=500, detail=f"No se pudo encolar: {e}")
    return {"status": "queued", "scope": scope}


@router.post("/trigger/purge", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def trigger_purge(db: AsyncSession = Depends(get_session)):
    job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
    ttl = job.purge_ttl_days if job else 30
    # Dev fallback: run inline if requested (no Redis needed)
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        try:
            # Run in a separate thread so images actor can call asyncio.run safely
            import anyio
            await anyio.to_thread.run_sync(lambda: purge_soft_deleted.fn(ttl))  # type: ignore[attr-defined]
            return {"status": "ran-inline", "ttl_days": ttl}
        except Exception as e:
            logger.exception("Fallo inline purge")
            raise HTTPException(status_code=500, detail=f"Fallo inline purge: {e}")
    try:
        purge_soft_deleted.send(ttl)
    except Exception as e:
        logger.exception("No se pudo encolar purge")
        raise HTTPException(status_code=500, detail=f"No se pudo encolar purge: {e}")
    return {"status": "queued", "ttl_days": ttl}


@router.get("/logs/stream", dependencies=[Depends(require_roles("admin"))])
async def stream_logs(last_id: int = Query(0, ge=0), poll_ms: int = Query(1200, ge=200, le=10000), db: AsyncSession = Depends(get_session)):
    """SSE stream de logs del crawler + progreso.

    En cada iteración:
      - Devuelve nuevos logs con id > last_id
      - Adjunta resumen de progreso básico (pending/processed/percent)
    """
    poll = max(0.2, min(poll_ms / 1000.0, 10.0))

    async def event_gen():  # pragma: no cover - streaming
        nonlocal last_id
        while True:
            try:
                # Obtener nuevos logs
                stmt = select(ImageJobLog).where(ImageJobLog.id > last_id).order_by(ImageJobLog.id.asc()).limit(200)
                rows = (await db.execute(stmt)).scalars().all()
                items = []
                for r in rows:
                    last_id = max(last_id, r.id)
                    items.append({
                        "id": r.id,
                        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                        "level": r.level,
                        "message": r.message,
                        "data": r.data or {},
                    })
                # Progreso ligero (sin recalcular logs recientes costosos)
                from db.models import Product, Image
                subq_has_img2 = select(Image.id).where(Image.product_id == Product.id, Image.active == True).exists()
                pending_now = (await db.execute(select(func.count()).select_from(Product).where(Product.stock > 0).where(~subq_has_img2))).scalar() or 0
                total_now = (await db.execute(select(func.count()).select_from(Product).where(Product.stock > 0))).scalar() or 0
                processed_now = (total_now - pending_now) if total_now >= pending_now else 0
                percent_now = int(round((processed_now / total_now) * 100)) if total_now else 0
                payload = {
                    "logs": items,
                    "last_id": last_id,
                    "progress": {
                        "total": total_now,
                        "pending": pending_now,
                        "processed": processed_now,
                        "percent": percent_now,
                    },
                }
                import json
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:  # client disconnected
                break
            except Exception as e:  # swallow and continue
                yield f"data: {{\"error\": \"{str(e)[:120]}\"}}\n\n"
            await asyncio.sleep(poll)
    return StreamingResponse(event_gen(), media_type="text/event-stream")
