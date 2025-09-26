# NG-HEADER: Nombre de archivo: tiendanube.py
# NG-HEADER: Ubicación: services/integrations/tiendanube.py
# NG-HEADER: Descripción: Integración backend con la API de Tiendanube.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import time
from typing import List, Dict
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Image, ExternalMediaMap


RATE_LIMIT_PER_MIN = 5


def _creds() -> tuple[str | None, str | None]:
    return os.getenv("TNUBE_API_TOKEN"), os.getenv("TNUBE_STORE_ID")


async def upload_product_images(product_id: int, db: AsyncSession) -> Dict:
    token, store_id = _creds()
    # collect active images sorted
    imgs = (
        await db.execute(
            select(Image).where(Image.product_id == product_id, Image.active == True).order_by(Image.sort_order.asc().nulls_last(), Image.id.asc())
        )
    ).scalars().all()
    if not imgs:
        return {"status": "no_images"}

    if not token or not store_id:
        # Dry-run mapping
        for im in imgs:
            db.add(ExternalMediaMap(product_id=product_id, provider="tiendanube", remote_media_id=f"dry-{im.id}"))
        await db.commit()
        return {"status": "dry_run", "count": len(imgs)}

    # Real push skeleton
    headers = {
        "Authentication": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "GrowenBot/1.0",
    }
    # Note: Tiendanube API specifics omitted; this is a placeholder
    url = f"https://api.tiendanube.com/v1/{store_id}/products/{product_id}/images"
    created: list[dict] = []
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for im in imgs:
            body = {"src": im.url}
            try:
                r = await client.post(url, json=body)
                if r.status_code in (200, 201):
                    rid = str(r.json().get("id") or r.json().get("image_id") or im.id)
                    db.add(ExternalMediaMap(product_id=product_id, provider="tiendanube", remote_media_id=rid))
                    await db.commit()
                    created.append({"image_id": im.id, "remote_id": rid})
                else:
                    # naive backoff
                    await db.commit()
            except Exception:
                pass
            # simple rate limit pacing
            time.sleep(60.0 / RATE_LIMIT_PER_MIN)
    return {"status": "ok", "created": created}


async def bulk_upload(product_ids: List[int], db: AsyncSession) -> Dict:
    results = []
    start = time.monotonic()
    sent_in_window = 0
    for pid in product_ids:
        res = await upload_product_images(pid, db)
        results.append({"product_id": pid, **res})
        sent_in_window += 1
        # enforce 5/min across products (coarse)
        if sent_in_window >= RATE_LIMIT_PER_MIN:
            elapsed = time.monotonic() - start
            if elapsed < 60:
                time.sleep(60 - elapsed)
            start = time.monotonic()
            sent_in_window = 0
    return {"results": results}

