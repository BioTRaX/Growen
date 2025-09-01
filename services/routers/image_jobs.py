# NG-HEADER: Nombre de archivo: image_jobs.py
# NG-HEADER: Ubicación: services/routers/image_jobs.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db.models import ImageJob, ImageJobLog
from db.session import get_session
from services.auth import require_roles, require_csrf


router = APIRouter(prefix="/admin/image-jobs", tags=["images"])


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
    running = False  # placeholder; real status comes from worker heartbeat
    pending = 0      # placeholder; would come from queue length
    last_logs = await db.execute(select(ImageJobLog).where(ImageJobLog.job_name == job.name).order_by(ImageJobLog.created_at.desc()).limit(10))
    logs = [
        {"level": l.level, "message": l.message, "created_at": l.created_at.isoformat()}
        for l in last_logs.scalars().all()
    ]
    return {
        "name": job.name,
        "active": job.active,
        "mode": job.mode,
        "running": running,
        "pending": pending,
        "logs": logs,
    }


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


# --- Triggers ---
from services.jobs.images import crawl_catalog_missing_images, purge_soft_deleted


@router.post("/trigger/crawl-missing", dependencies=[Depends(require_csrf), Depends(require_roles("admin", "colaborador"))])
async def trigger_crawl_missing(scope: str = Query("stock"), db: AsyncSession = Depends(get_session)):
    try:
        if scope not in ("stock", "all"):
            raise HTTPException(status_code=400, detail="scope inválido")
        crawl_catalog_missing_images.send(scope)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo encolar: {e}")
    return {"status": "queued", "scope": scope}


@router.post("/trigger/purge", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def trigger_purge(db: AsyncSession = Depends(get_session)):
    job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
    ttl = job.purge_ttl_days if job else 30
    try:
        purge_soft_deleted.send(ttl)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo encolar purge: {e}")
    return {"status": "queued", "ttl_days": ttl}
