from __future__ import annotations

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from db.models import Product, Image, ImageVersion, ImageReview
from services.media import get_media_root
from services.media.downloader import download_product_image, DownloadError
from services.media.processor import to_square_webp_set
from services.scrapers.santaplanta import search_by_title, extract_product_image
from services.scrapers.fallback import search_image_urls_bing


async def ensure_product_image(product_id: int, db: AsyncSession) -> Optional[int]:
    """If the product has no active images, try to find and attach one.

    Returns image_id if created, else None.
    """
    has = await db.scalar(select(Image.id).where(Image.product_id == product_id, Image.active == True))
    if has:
        return None
    prod = await db.get(Product, product_id)
    if not prod:
        return None
    title = prod.title or ""
    # 1) Provider search
    urls = await search_by_title(title)
    img_url: Optional[str] = None
    for u in urls:
        img_url = await extract_product_image(u)
        if img_url:
            break
    # 2) Fallback: Bing image search
    if not img_url:
        try:
            candidates = await search_image_urls_bing(title, top=3)
            if candidates:
                img_url = candidates[0]
        except Exception:
            pass
    if not img_url:
        return None
    # Download + attach
    dl = await download_product_image(product_id, img_url)
    root = get_media_root()
    rel = str(dl.path.relative_to(root))
    img = Image(product_id=product_id, url=f"/media/{rel}", path=rel, mime=dl.mime, bytes=dl.size)
    db.add(img)
    await db.flush()
    db.add(ImageVersion(image_id=img.id, kind="original", path=rel, size_bytes=img.bytes, mime=img.mime, source_url=img_url))
    # Derivatives
    out_dir = root / "Productos" / str(product_id) / "derived"
    base = "-".join([p for p in [prod.slug or None, prod.sku_root or None] if p]) or f"prod-{product_id}"
    proc = to_square_webp_set(dl.path, out_dir, base)
    for kind, pth, px in (("thumb", proc.thumb, 256), ("card", proc.card, 800), ("full", proc.full, 1600)):
        relv = str(pth.relative_to(root))
        db.add(ImageVersion(image_id=img.id, kind=kind, path=relv, width=px, height=px, mime="image/webp"))
    db.add(ImageReview(image_id=img.id, status="pending"))
    await db.commit()
    return img.id

