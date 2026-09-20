#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: meli.py
# NG-HEADER: Ubicación: services/routers/meli.py
# NG-HEADER: Descripción: Administración autenticada de OAuth y vínculos de stock MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MeliAccount, MeliItemLink, Product
from db.session import get_session
from services.auth import SessionData, require_csrf, require_roles
from services.meli.crypto import TokenCipher
from services.meli.jobs import enqueue_stock_sync, process_job
from services.meli.oauth import create_authorization
from services.meli.schemas import ItemLinkCreate
from services.meli.settings import load_meli_runtime_config


router = APIRouter(prefix="/integrations/meli", tags=["meli"])


@router.post("/oauth/authorizations", dependencies=[Depends(require_csrf)])
async def begin_oauth(
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    request = await create_authorization(
        db,
        requested_by_user_id=session_data.user.id if session_data.user else None,
        config=load_meli_runtime_config(),
        cipher=TokenCipher.from_runtime(),
    )
    return {"authorization_url": request.authorization_url, "expires_at": request.expires_at}


@router.post("/item-links", dependencies=[Depends(require_csrf)])
async def create_item_link(
    payload: ItemLinkCreate,
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    account = await db.get(MeliAccount, payload.account_id)
    product = await db.get(Product, payload.product_id)
    if account is None or account.status != "active":
        raise HTTPException(status_code=404, detail="meli_account_not_found")
    if product is None:
        raise HTTPException(status_code=404, detail="product_not_found")
    existing = await db.scalar(
        select(MeliItemLink).where(
            MeliItemLink.account_id == payload.account_id,
            MeliItemLink.item_id == payload.item_id,
            MeliItemLink.variation_id == payload.variation_id,
        )
    )
    link = existing or MeliItemLink(**payload.model_dump())
    link.active = True
    if existing is None:
        db.add(link)
        await db.commit()
        await db.refresh(link)
    job = await enqueue_stock_sync(db, link_id=link.id)
    if os.getenv("RUN_INLINE_JOBS", "0") == "1":
        from services.meli.client import MeliClient

        config = load_meli_runtime_config()
        client = MeliClient(config)
        try:
            await process_job(db, job_id=job.id, client=client, cipher=TokenCipher.from_runtime())
        finally:
            await client.aclose()
    else:
        from workers.meli_sync import process_meli_job

        process_meli_job.send(job.id)
    return {"link_id": link.id, "job_id": job.id, "status": job.status}
