# NG-HEADER: Nombre de archivo: images.py
# NG-HEADER: Ubicación: services/routers/images.py
# NG-HEADER: Descripción: API REST de imágenes y sus metadatos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from pathlib import Path

from db.models import Image, ImageVersion, ImageReview, Product, AuditLog, ExternalMediaMap
from db.session import get_session
from services.auth import require_roles, require_csrf, current_session, SessionData
from services.media import get_media_root, save_upload
from services.media.downloader import download_product_image, DownloadError, _clamav_scan
from services.media.processor import to_square_webp_set, apply_watermark, remove_bg
from services.media.seo import gen_alt_title
from services.integrations.tiendanube import upload_product_images, bulk_upload
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


router = APIRouter(prefix="/products", tags=["images"])


async def _audit(db: AsyncSession, action: str, table: str, entity_id: int | None, meta: dict | None, sess: SessionData, req: Request) -> None:
    db.add(
        AuditLog(
            action=action,
            table=table,
            entity_id=entity_id,
            meta=meta,
            user_id=sess.user.id if sess.user else None,
            ip=(req.client.host if req.client else None),
        )
    )


class FromUrlIn(BaseModel):
    url: str
    generate_derivatives: bool = True


@router.post(
    "/{pid}/images/upload",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def upload_image(
    pid: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    # Verificar disponibilidad de Pillow (entorno)
    if not PIL_AVAILABLE:
        # Auditar y devolver mensaje claro para el operador
        try:
            await _audit(db, "upload_env_missing", "images", None, {"product_id": pid, "filename": getattr(file, 'filename', None)}, sess, request)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Entorno de imágenes incompleto: Pillow no está disponible. Verifique requirements e instalación.")
    prod = await db.get(Product, pid)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    # Correlation id for diagnostics
    import uuid as _uuid
    cid = _uuid.uuid4().hex
    try:
        await _audit(db, "upload_start", "images", None, {"product_id": pid, "filename": file.filename, "content_type": file.content_type, "cid": cid}, sess, request)
    except Exception:
        pass
    # Basic type gate
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type and file.content_type not in allowed:
        try:
            await _audit(db, "upload_type_block", "images", None, {"product_id": pid, "cid": cid, "content_type": file.content_type}, sess, request)
        except Exception:
            pass
        raise HTTPException(status_code=415, detail="Tipo de archivo no permitido")
    path, sha256 = await save_upload(f"Productos/{pid}/raw", file.filename, file)
    try:
        await _audit(db, "upload_saved", "images", None, {"product_id": pid, "cid": cid, "path": str(path), "sha256": sha256}, sess, request)
    except Exception:
        pass
    # Size validation (<=10MB) and dimensions (>= min)
    size = path.stat().st_size
    if size > 10 * 1024 * 1024:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            await _audit(db, "upload_too_large", "images", None, {"product_id": pid, "cid": cid, "bytes": int(size)}, sess, request)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (>10MB)")
    min_side = int(os.getenv("IMAGE_MIN_SIZE", "600"))
    try:
        with PILImage.open(path) as im:
            w, h = im.size
        if w < min_side or h < min_side:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"Resolucion insuficiente (<{min_side}x{min_side})")
    except HTTPException:
        try:
            await _audit(db, "upload_invalid_dimensions", "images", None, {"product_id": pid, "cid": cid}, sess, request)
        except Exception:
            pass
        raise
    except Exception:
        # Not an image or unreadable
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            await _audit(db, "upload_invalid_image", "images", None, {"product_id": pid, "cid": cid}, sess, request)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Archivo de imagen invalido")
    # Optional AV scan
    try:
        await _clamav_scan(path)
    except Exception as e:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            await _audit(db, "upload_av_blocked", "images", None, {"product_id": pid, "cid": cid, "error": str(e)}, sess, request)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))
    # ensure product slug exists to name derivatives
    if not prod.slug:
        import re
        base = (prod.title or f"prod-{pid}").lower()
        base = re.sub(r"[^a-z0-9\s-]", "", base)
        base = re.sub(r"[\s_-]+", "-", base).strip("-")
        prod.slug = base[:200]
        db.add(prod)
    rel = str(path.relative_to(get_media_root()))
    rel_norm = rel.replace('\\', '/')
    img = Image(
        product_id=pid,
        url=f"/media/{rel_norm}",
        path=rel,
        mime=file.content_type or None,
        bytes=size,
        checksum_sha256=sha256,
    )
    db.add(img)
    await db.flush()
    db.add(ImageVersion(image_id=img.id, kind="original", path=rel, size_bytes=img.bytes, mime=img.mime))
    # Generate default derivatives (thumb/card/full as WebP square)
    try:
        root = get_media_root()
        base = "-".join([p for p in [prod.slug or None, prod.sku_root or None] if p]) or f"prod-{pid}"
        out_dir = root / "Productos" / str(pid) / "derived"
        proc = to_square_webp_set(path, out_dir, base)
        for kind, pth, px in (
            ("thumb", proc.thumb, 256),
            ("card", proc.card, 800),
            ("full", proc.full, 1600),
        ):
            relv = str(pth.relative_to(root)).replace('\\', '/')
            db.add(ImageVersion(image_id=img.id, kind=kind, path=relv, width=px, height=px, mime="image/webp"))
    except Exception:
        # Derivative generation is best-effort; log via audit and continue
        await _audit(db, "derive_error", "images", img.id if 'img' in locals() else None, {"product_id": pid, "cid": cid, "filename": file.filename}, sess, request)
    try:
        await _audit(db, "upload_image", "images", img.id, {"product_id": pid, "filename": file.filename, "size": size, "cid": cid}, sess, request)
    except Exception:
        pass
    # Si no hay imagen primaria activa, establecer ésta como primaria
    try:
        # Buscar si existe alguna imagen activa primaria para el producto
        has_primary = (await db.execute(select(Image).where(Image.product_id == pid, Image.active == True, Image.is_primary == True).limit(1))).first()
        if not has_primary:
            # Asegurar que todas las demás queden en False y marcar esta como primaria
            from sqlalchemy import update as _update
            await db.execute(_update(Image).where(Image.product_id == pid).values(is_primary=False))
            img.is_primary = True
            await _audit(db, "auto_set_primary", "images", img.id, {"product_id": pid}, sess, request)
    except Exception:
        pass
    await db.commit()
    await db.refresh(img)
    return {"image_id": img.id, "url": img.url, "path": img.path, "correlation_id": cid}


@router.post(
    "/{pid}/images/from-url",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def image_from_url(
    pid: int,
    request: Request,
    payload: FromUrlIn,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    prod = await db.get(Product, pid)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    try:
        dl = await download_product_image(pid, payload.url)
    except DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ensure product slug exists
    if not prod.slug:
        import re
        base = (prod.title or f"prod-{pid}").lower()
        base = re.sub(r"[^a-z0-9\s-]", "", base)
        base = re.sub(r"[\s_-]+", "-", base).strip("-")
        prod.slug = base[:200]
        db.add(prod)
    rel = str(dl.path.relative_to(get_media_root()))
    rel_norm = rel.replace('\\', '/')
    img = Image(
        product_id=pid,
        url=f"/media/{rel_norm}",
        path=rel,
        mime=dl.mime,
        bytes=dl.size,
        checksum_sha256=dl.sha256,
    )
    db.add(img)
    await db.flush()
    db.add(
        ImageVersion(
            image_id=img.id, kind="original", path=rel, size_bytes=img.bytes, mime=img.mime, source_url=payload.url
        )
    )
    db.add(ImageReview(image_id=img.id, status="pending"))
    await _audit(db, "download", "images", img.id, {"url": payload.url}, sess, request)

    # Derivatives
    if payload.generate_derivatives:
        root = get_media_root()
        base = "-".join([p for p in [prod.slug or None, prod.sku_root or None] if p]) or f"prod-{pid}"
        out_dir = root / "Productos" / str(pid) / "derived"
        try:
            proc = to_square_webp_set(dl.path, out_dir, base)
            for kind, pth, px in (
                ("thumb", proc.thumb, 256),
                ("card", proc.card, 800),
                ("full", proc.full, 1600),
            ):
                relv = str(pth.relative_to(root)).replace('\\', '/')
                db.add(
                    ImageVersion(image_id=img.id, kind=kind, path=relv, width=px, height=px, mime="image/webp")
                )
        except Exception:
            await _audit(db, "derive_error", "images", img.id, {"url": payload.url}, sess, request)
    await db.commit()
    await db.refresh(img)
    return {"image_id": img.id, "url": img.url}


@router.post(
    "/{pid}/images/{iid}/set-primary",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def set_primary(pid: int, iid: int, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    img = await db.get(Image, iid)
    if not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    await db.execute(update(Image).where(Image.product_id == pid).values(is_primary=False))
    img.is_primary = True
    await _audit(db, "set_primary", "images", iid, {"product_id": pid}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.post(
    "/{pid}/images/{iid}/lock",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def lock_image(pid: int, iid: int, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    img = await db.get(Image, iid)
    if not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    img.locked = not bool(img.locked)
    await _audit(db, "lock", "images", iid, {"product_id": pid}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.delete(
    "/{pid}/images/{iid}",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def delete_image(pid: int, iid: int, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    img = await db.get(Image, iid)
    if not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    img.active = False
    await _audit(db, "soft_delete", "images", iid, {"product_id": pid}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.get(
    "/{pid}/images/audit-logs",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def image_audit_logs(pid: int, db: AsyncSession = Depends(get_session), limit: int = Query(50, ge=1, le=500)) -> dict:
    """Auditoría reciente de acciones de imágenes para el producto pid."""
    from sqlalchemy import join
    j = join(AuditLog, Image, AuditLog.entity_id == Image.id)
    rows = (await db.execute(
        select(AuditLog, Image.id.label("image_id")).select_from(j)
        .where(Image.product_id == pid, AuditLog.table == "images")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )).all()
    items = [
        {
            "action": a.action,
            "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else None,
            "meta": a.meta or {},
            "image_id": img_id,
        }
        for a, img_id in rows
    ]
    return {"items": items}


class ReorderIn(BaseModel):
    image_ids: List[int]


@router.post(
    "/{pid}/images/reorder",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def reorder_images(pid: int, payload: ReorderIn, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    res = await db.execute(select(Image).where(Image.product_id == pid, Image.id.in_(payload.image_ids)))
    imgs = res.scalars().all()
    if len(imgs) != len(payload.image_ids):
        raise HTTPException(status_code=400, detail="IDs invalidos o no pertenecen al producto")
    for idx, iid in enumerate(payload.image_ids):
        for im in imgs:
            if im.id == iid:
                im.sort_order = idx
                break
    # set first as primary
    if payload.image_ids:
        await db.execute(update(Image).where(Image.product_id == pid).values(is_primary=False))
        for im in imgs:
            if im.id == payload.image_ids[0]:
                im.is_primary = True
                break
    await _audit(db, "reorder", "images", None, {"product_id": pid, "order": payload.image_ids}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.post(
    "/{pid}/images/{iid}/process/remove-bg",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def process_remove_bg(pid: int, iid: int, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    img = await db.get(Image, iid)
    if not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    if not img.path:
        raise HTTPException(status_code=400, detail="Imagen sin archivo local")
    root = get_media_root()
    src = root / img.path
    out = remove_bg(src, dest_dir=root / "Productos" / str(pid) / "derived")
    rel = str(out.relative_to(get_media_root()))
    db.add(ImageVersion(image_id=img.id, kind="bg_removed", path=rel))
    await _audit(db, "remove_bg", "images", iid, None, sess, request)
    await db.commit()
    return {"status": "ok", "path": rel}


class WatermarkIn(BaseModel):
    position: Optional[str] = "br"
    opacity: Optional[float] = 0.18


@router.post(
    "/{pid}/images/{iid}/process/watermark",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def process_watermark(
    pid: int,
    iid: int,
    request: Request,
    payload: WatermarkIn,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    img = await db.get(Image, iid)
    if not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    if not img.path:
        raise HTTPException(status_code=400, detail="Imagen sin archivo local")
    root = get_media_root()
    src = root / img.path
    logo_env = os.getenv("WATERMARK_LOGO")
    logo = Path(logo_env) if logo_env else (root / "Logos" / "logo.png")
    if not logo.exists():
        raise HTTPException(status_code=400, detail="Logo de watermark no encontrado")
    out = apply_watermark(src, logo, pos=payload.position or "br", opacity=payload.opacity or 0.18, dest_dir=root / "Productos" / str(pid) / "derived")
    rel = str(out.relative_to(root))
    db.add(ImageVersion(image_id=img.id, kind="watermarked", path=rel))
    await _audit(db, "watermark", "images", iid, {"position": payload.position, "opacity": payload.opacity}, sess, request)
    await db.commit()
    return {"status": "ok", "path": rel}


@router.post(
    "/{pid}/images/{iid}/seo/refresh",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def seo_refresh(pid: int, iid: int, db: AsyncSession = Depends(get_session)):
    prod = await db.get(Product, pid)
    img = await db.get(Image, iid)
    if not prod or not img or img.product_id != pid:
        raise HTTPException(status_code=404, detail="No encontrado")
    data = gen_alt_title({"title": prod.title})
    img.alt_text = data["alt"]
    img.title_text = data["title"]
    # Generate slug if missing
    if not prod.slug:
        import re
        base = prod.title.lower()
        base = re.sub(r"[^a-z0-9\s-]", "", base)
        base = re.sub(r"[\s_-]+", "-", base).strip("-")
        prod.slug = base[:200]
    await db.commit()
    return data


@router.get(
    "/images/review",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def list_review(status: str = "pending", db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(ImageReview, Image).join(Image, Image.id == ImageReview.image_id).where(ImageReview.status == status)
    )
    rows = res.all()
    return [
        {
            "image_id": img.id,
            "product_id": img.product_id,
            "status": rev.status,
            "path": img.path,
        }
        for rev, img in rows
    ]


@router.post(
    "/images/{iid}/review/approve",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def approve(iid: int, request: Request, lock: bool = False, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    rev = await db.scalar(select(ImageReview).where(ImageReview.image_id == iid))
    if not rev:
        rev = ImageReview(image_id=iid, status="approved")
        db.add(rev)
    else:
        rev.status = "approved"
    img = await db.get(Image, iid)
    if lock and img:
        img.locked = True
    await _audit(db, "review_approve", "images", iid, {"lock": lock}, sess, request)
    await db.commit()
    return {"status": "ok"}


class RejectIn(BaseModel):
    note: Optional[str] = None
    soft_delete: Optional[bool] = False


@router.post(
    "/images/{iid}/review/reject",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def reject(iid: int, payload: RejectIn, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    rev = await db.scalar(select(ImageReview).where(ImageReview.image_id == iid))
    if not rev:
        rev = ImageReview(image_id=iid, status="rejected", note=payload.note)
        db.add(rev)
    else:
        rev.status = "rejected"
        rev.note = payload.note
    if payload.soft_delete:
        img = await db.get(Image, iid)
        if img:
            img.active = False
    await _audit(db, "review_reject", "images", iid, {"note": payload.note, "soft_delete": payload.soft_delete}, sess, request)
    await db.commit()
    return {"status": "ok"}


class PushBulkIn(BaseModel):
    product_ids: List[int]


@router.post(
    "/{pid}/images/push/tiendanube",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def push_tn_single(pid: int, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    res = await upload_product_images(pid, db)
    await _audit(db, "push_tn_single", "images", None, {"product_id": pid, **res}, sess, request)
    return res


@router.post(
    "/images/push/tiendanube/bulk",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def push_tn_bulk(payload: PushBulkIn, request: Request, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    res = await bulk_upload(payload.product_ids, db)
    await _audit(db, "push_tn_bulk", "images", None, {"count": len(payload.product_ids)}, sess, request)
    return res
