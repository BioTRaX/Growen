# NG-HEADER: Nombre de archivo: images.py
# NG-HEADER: Ubicación: services/jobs/images.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import dramatiq

from db.session import SessionLocal
from db.models import Product, Image, ImageReview, ImageJobLog, ImageJob
from services.media.downloader import download_product_image
from services.media.processor import to_square_webp_set
from services.media import get_media_root
from services.scrapers.santaplanta import search_by_title, extract_product_image
from services.media.orchestrator import ensure_product_image
from services.notifications.telegram import send_message


logger = logging.getLogger(__name__)


def _within_window(job: ImageJob) -> bool:
    """Check if current time is within the configured window when mode=='window'.
    Window is interpreted in GMT-3.
    """
    if job.mode != "window":
        return True
    try:
        import datetime as dt

        tz = dt.timezone(dt.timedelta(hours=-3))
        now = dt.datetime.now(tz).time()
        if job.window_start and job.window_end:
            return job.window_start <= now <= job.window_end
    except Exception:
        return True
    return True


@dramatiq.actor(max_retries=3)
def crawl_product_missing_image(product_id: int) -> None:
    async def _run() -> None:
        async with SessionLocal() as db:
            job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
            if job and job.active is False:
                return
            if job and job.mode == "window" and not _within_window(job):
                return
            try:
                new_id = await ensure_product_image(product_id, db)
                if new_id:
                    db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="downloaded", data={"product_id": product_id}))
                    await db.commit()
                    try:
                        import asyncio as aio
                        aio.create_task(send_message(f"Imagen descargada (pending review) para producto {product_id}"))
                    except Exception:
                        pass
            except Exception as e:  # best-effort
                db.add(ImageJobLog(job_name="imagenes_productos", level="ERROR", message=str(e), data={"product_id": product_id}))
                await db.commit()
    import asyncio
    asyncio.run(_run())


@dramatiq.actor(max_retries=3)
def crawl_catalog_missing_images(scope: str = "stock") -> None:
    async def _run() -> None:
        async with SessionLocal() as db:
            job = await db.scalar(select(ImageJob).where(ImageJob.name == "imagenes_productos"))
            if job and job.active is False:
                return
            if job and job.mode == "window" and not _within_window(job):
                return
            # Iterate products without active images (limit to protect load)
            base = select(Product.id).where(~Product.id.in_(select(Image.product_id).where(Image.active == True)))
            if scope == "stock":
                from sqlalchemy import and_
                base = base.where((Product.stock != None) & (Product.stock > 0))  # type: ignore
            q = base.limit(50)
            ids = [row[0] for row in (await db.execute(q)).all()]
            for pid in ids:
                try:
                    await ensure_product_image(pid, db)
                except Exception as e:
                    db.add(ImageJobLog(job_name="imagenes_productos", level="ERROR", message=str(e), data={"product_id": pid}))
                    await db.commit()
    import asyncio
    asyncio.run(_run())


@dramatiq.actor(max_retries=3)
def purge_soft_deleted(ttl_days: int = 30) -> None:
    async def _run() -> None:
        import datetime as dt
        async with SessionLocal() as db:
            cutoff = dt.datetime.utcnow() - dt.timedelta(days=ttl_days)
            # Delete images inactive older than cutoff; cascade removes versions
            q = select(Image).where(Image.active == False, Image.updated_at < cutoff)
            imgs = (await db.execute(q)).scalars().all()
            for im in imgs:
                await db.delete(im)
            await db.commit()
            if imgs:
                db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="purged", data={"count": len(imgs)}))
                await db.commit()
    import asyncio
    asyncio.run(_run())
