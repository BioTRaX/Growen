# NG-HEADER: Nombre de archivo: orchestrator.py
# NG-HEADER: Ubicación: services/media/orchestrator.py
# NG-HEADER: Descripción: Orquestador de pipelines de media y transformaciones.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path

from db.models import Product, Image, ImageVersion, ImageReview, ImageJobLog
from services.media import get_media_root
from services.media.downloader import download_product_image, DownloadError
from services.media.processor import to_square_webp_set
from services.scrapers.santaplanta import search_by_title, extract_product_image
from services.scrapers.fallback import search_image_urls_bing
from services.images.crawler import crawl_best_images
from services.logging.ctx_logger import make_correlation_id, log_event


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
    # small helper to log progress consistently
    def _log(stage: str, level: str = "INFO", details: Dict[str, Any] | None = None) -> None:
        try:
            db.add(ImageJobLog(job_name="imagenes_productos", level=level, message=stage, data={"product_id": product_id, "title": title, **(details or {})}))
        except Exception:
            pass

    cid = make_correlation_id()
    _log("start")
    try:
        await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step="start", title=title)
    except Exception:
        pass
    # 1) Hybrid picks (requests -> Playwright) for primary + seconds
    picks = await crawl_best_images(title, correlation_id=cid, db=db)
    img_url: Optional[str] = picks.get("primary") if isinstance(picks, dict) else None
    sec_urls = (picks.get("seconds") if isinstance(picks, dict) else []) or []
    if not img_url:
        # 2) Fallback: Bing image search
        try:
            candidates = await search_image_urls_bing(title, top=3)
            if candidates:
                img_url = candidates[0]
                _log("fallback_bing", details={"candidates": candidates})
                try:
                    await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step="fallback_bing", candidates=candidates)
                except Exception:
                    pass
        except Exception:
            pass
    if not img_url:
        _log("no_candidate", level="WARN")
        try:
            await log_event(db, level="WARN", correlation_id=cid, product_id=product_id, step="no_candidate")
        except Exception:
            pass
        return None
    # Download + attach
    dl = await download_product_image(product_id, img_url)
    _log("download_ok", details={"mime": dl.mime, "bytes": dl.size})
    try:
        await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step="download_ok", mime=dl.mime, bytes=dl.size)
    except Exception:
        pass

    # Deduplicate by checksum for this product
    try:
        exists_same = await db.scalar(
            select(Image.id).where(Image.product_id == product_id, Image.checksum_sha256 == dl.sha256)
        )
        if exists_same:
            _log("duplicate_skip", level="INFO", details={"image_id": exists_same})
            return None
    except Exception:
        # non-fatal
        pass
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
    _log("derivatives_done", details={"image_id": img.id})
    try:
        await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step="derivatives_done", image_id=img.id)
    except Exception:
        pass
    # Attach up to 2 secondary images
    try:
        for surl in sec_urls[:2]:
            try:
                dl2 = await download_product_image(product_id, surl)
                exists_same = await db.scalar(select(Image.id).where(Image.product_id == product_id, Image.checksum_sha256 == dl2.sha256))
                if exists_same:
                    continue
                rel2 = str(dl2.path.relative_to(root))
                im2 = Image(product_id=product_id, url=f"/media/{rel2}", path=rel2, mime=dl2.mime, bytes=dl2.size)
                db.add(im2)
                await db.flush()
                db.add(ImageVersion(image_id=im2.id, kind="original", path=rel2, size_bytes=im2.bytes, mime=im2.mime, source_url=surl))
                proc2 = to_square_webp_set(dl2.path, out_dir, base)
                for kind, pth, px in (("thumb", proc2.thumb, 256), ("card", proc2.card, 800), ("full", proc2.full, 1600)):
                    db.add(ImageVersion(image_id=im2.id, kind=kind, path=str(pth.relative_to(root)), width=px, height=px, mime="image/webp"))
            except Exception:
                pass
    except Exception:
        pass
    await db.commit()
    _log("done", details={"image_id": img.id})
    try:
        await log_event(db, level="INFO", correlation_id=cid, product_id=product_id, step="done", image_id=img.id)
    except Exception:
        pass
    return img.id

