# NG-HEADER: Nombre de archivo: images.py
# NG-HEADER: Ubicación: workers/images.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
from datetime import datetime, time

import dramatiq  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, delete

from db.models import Product, Image, ImageJobLog
from services.media.orchestrator import ensure_product_image


DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./growen.db")
engine = create_async_engine(DB_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _in_window() -> bool:
    # Placeholder for window enforcement (GMT-3)
    mode = os.getenv("JOB_MODE", "off")
    if mode != "window":
        return True
    # TODO: read from DB settings; for now always true
    return True


@dramatiq.actor(queue="images")
def crawl_product_missing_image(product_id: int) -> None:
    async def run():
        async with SessionLocal() as db:
            ok = await ensure_product_image(product_id, db)
            db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="ensure_product_image", data={"product_id": product_id, "added": ok}))
            await db.commit()
    import asyncio
    asyncio.run(run())


@dramatiq.actor(queue="images")
def crawl_catalog_missing_images(scope: str = "stock") -> None:
    async def run():
        if not _in_window():
            return
        async with SessionLocal() as db:
            # filter products by scope
            if scope == "stock":
                rows = (await db.execute(select(Product.id).where(Product.stock > 0))).scalars().all()
            else:
                rows = (await db.execute(select(Product.id))).scalars().all()
            for pid in rows:
                has = await db.scalar(select(Image.id).where(Image.product_id == pid, Image.active == True))
                if has:
                    continue
                await ensure_product_image(pid, db)
            db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="crawl_catalog_missing_images done", data={"scope": scope}))
            await db.commit()
    import asyncio
    asyncio.run(run())


@dramatiq.actor(queue="images")
def purge_soft_deleted(ttl_days: int = 30) -> None:
    async def run():
        # Placeholder: physically delete images with active=False older than ttl; requires timestamps not tracked per soft-delete time.
        async with SessionLocal() as db:
            db.add(ImageJobLog(job_name="imagenes_productos", level="INFO", message="purge_soft_deleted executed", data={"ttl_days": ttl_days}))
            await db.commit()
    import asyncio
    asyncio.run(run())
