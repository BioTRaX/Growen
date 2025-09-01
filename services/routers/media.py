# NG-HEADER: Nombre de archivo: media.py
# NG-HEADER: Ubicación: services/routers/media.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Media endpoints: minimal upload for testing static serving.

These are basic and admin-only; a fuller pipeline will replace them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pathlib import Path

from db.session import get_session
from db.models import Product, Image
from services.auth import require_roles, require_csrf
from services.media import save_upload, get_media_root


router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def upload_media(
    product_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    prod = await session.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    path, sha256 = await save_upload("products", file.filename, file)
    rel_path = str(path.relative_to(get_media_root()))

    img = Image(
        product_id=product_id,
        url=f"/media/{rel_path.replace('\\', '/')}",
        path=rel_path,
        mime=file.content_type or None,
        bytes=path.stat().st_size,
        checksum_sha256=sha256,
    )
    session.add(img)
    await session.commit()
    await session.refresh(img)

    return {
        "image_id": img.id,
        "url": img.url,
        "path": img.path,
        "bytes": img.bytes,
        "mime": img.mime,
        "sha256": img.checksum_sha256,
    }
