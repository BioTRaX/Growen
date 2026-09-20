#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: jobs.py
# NG-HEADER: Ubicación: services/meli/jobs.py
# NG-HEADER: Descripción: Outbox y deduplicación de trabajos exclusivos de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Crea trabajo durable antes de entregar su identificador a Dramatiq."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MeliAccount, MeliItemLink, MeliNotification, MeliSyncJob
from services.meli.crypto import TokenCipher
from services.meli.stock import MeliStockError, get_access_token, sync_stock_link


async def enqueue_stock_sync(db: AsyncSession, *, link_id: int) -> MeliSyncJob:
    """Devuelve el trabajo activo existente o crea uno nuevo para el vínculo."""

    link = await db.get(MeliItemLink, link_id)
    if link is None or not link.active:
        raise ValueError("meli_item_link_inactive")

    existing = (
        await db.execute(
            select(MeliSyncJob)
            .where(
                MeliSyncJob.kind == "stock",
                MeliSyncJob.item_link_id == link_id,
                MeliSyncJob.status.in_(("queued", "running")),
            )
            .order_by(MeliSyncJob.created_at.asc())
            .with_for_update()
        )
    ).scalars().first()
    if existing is not None:
        return existing

    job_id = uuid4().hex
    job = MeliSyncJob(
        id=job_id,
        dedupe_key=f"stock:{link_id}:{job_id}",
        kind="stock",
        account_id=link.account_id,
        item_link_id=link_id,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def process_job(
    db: AsyncSession,
    *,
    job_id: str,
    client: Any,
    cipher: TokenCipher,
) -> MeliSyncJob:
    """Reclama y procesa un job; el webhook nunca ejecuta esta lógica pesada."""

    job = (
        await db.execute(
            select(MeliSyncJob).where(MeliSyncJob.id == job_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("meli_job_not_found")
    if job.status in ("succeeded", "skipped"):
        return job
    if job.status == "running":
        return job
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.attempts += 1
    await db.commit()

    try:
        if job.kind == "stock" and job.item_link_id is not None:
            result = await sync_stock_link(
                db, link_id=job.item_link_id, client=client, cipher=cipher
            )
            job.payload_json = {"quantity": result.quantity, "item_id": result.item_id}
        elif job.kind == "notification" and job.notification_id:
            notice = await db.get(MeliNotification, job.notification_id)
            account = (
                await db.scalar(
                    select(MeliAccount)
                    .where(MeliAccount.id == job.account_id)
                    .with_for_update()
                )
                if job.account_id
                else None
            )
            if notice is None:
                raise ValueError("meli_notification_not_found")
            if account is None:
                notice.status = "skipped"
                notice.error_code = "meli_account_not_authorized"
                job.status = "skipped"
            else:
                token = await get_access_token(account, client=client, cipher=cipher)
                resource = await client.get_resource(notice.resource, token)
                owner = resource.get("seller_id") or resource.get("user_id")
                if owner is not None and int(owner) != account.seller_id:
                    raise ValueError("meli_resource_owner_mismatch")
                # Sólo deja evidencia de despacho verificado; no genera respuestas IA.
                job.payload_json = {
                    "topic": notice.topic,
                    "resource": notice.resource,
                    "verified_for_ai_dispatch": notice.topic in {"questions", "messages"},
                }
                notice.status = "succeeded"
                notice.completed_at = datetime.utcnow()
        else:
            raise ValueError("meli_job_kind_invalid")
        if job.status != "skipped":
            job.status = "succeeded"
        job.error_code = None
        job.error_message = None
        job.completed_at = datetime.utcnow()
        await db.commit()
        return job
    except Exception as exc:
        job.status = "failed"
        job.error_code = str(exc)[:64] if isinstance(exc, (ValueError, MeliStockError)) else "meli_job_failed"
        job.error_message = job.error_code
        job.completed_at = datetime.utcnow()
        await db.commit()
        raise
