#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: webhooks.py
# NG-HEADER: Ubicación: services/meli/webhooks.py
# NG-HEADER: Descripción: Validación, deduplicación y outbox de notificaciones Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Las notificaciones sólo despiertan consultas autenticadas posteriores."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MeliAccount, MeliNotification, MeliSyncJob
from services.meli.schemas import MeliNotificationPayload
from services.meli.settings import MeliRuntimeConfig


RESOURCE_RE = re.compile(r"^/(?:items|orders|questions|messages|claims|shipments|payments|packs|users)/[A-Za-z0-9_./-]+$")


class MeliWebhookError(RuntimeError):
    """El sobre recibido no cumple el contrato mínimo seguro."""


@dataclass(frozen=True)
class IngestResult:
    notification_id: str
    job_id: str | None
    duplicate: bool


async def ingest_notification(
    db: AsyncSession, *, payload: dict, config: MeliRuntimeConfig
) -> IngestResult:
    try:
        notice = MeliNotificationPayload.model_validate(payload)
    except ValidationError as exc:
        raise MeliWebhookError("meli_webhook_payload_invalid") from exc
    app_id = str(notice.application_id)
    if app_id != config.app_id.get_secret_value():
        raise MeliWebhookError("meli_webhook_application_invalid")
    if notice.topic not in config.allowed_topics:
        raise MeliWebhookError("meli_webhook_topic_not_allowed")
    if ".." in notice.resource or not RESOURCE_RE.fullmatch(notice.resource):
        raise MeliWebhookError("meli_webhook_resource_invalid")
    existing = await db.get(MeliNotification, notice.notification_id)
    if existing is not None:
        job = await db.scalar(select(MeliSyncJob).where(MeliSyncJob.notification_id == existing.id))
        return IngestResult(existing.id, job.id if job else None, True)
    account = await db.scalar(
        select(MeliAccount).where(
            MeliAccount.application_id == app_id,
            MeliAccount.seller_id == notice.user_id,
            MeliAccount.status == "active",
        )
    )
    notification = MeliNotification(
        id=notice.notification_id,
        account_id=account.id if account else None,
        application_id=app_id,
        seller_id=notice.user_id,
        topic=notice.topic,
        resource=notice.resource,
        attempts=notice.attempts,
        sent_at=notice.sent.replace(tzinfo=None) if notice.sent else None,
    )
    job_id = uuid4().hex
    job = MeliSyncJob(
        id=job_id,
        dedupe_key=f"notification:{notice.notification_id}",
        kind="notification",
        account_id=account.id if account else None,
        notification_id=notice.notification_id,
        payload_json={"topic": notice.topic, "resource": notice.resource},
    )
    db.add_all([notification, job])
    try:
        await db.commit()
    except IntegrityError:
        # Otra réplica pudo insertar el mismo _id entre la lectura y el commit.
        await db.rollback()
        existing = await db.get(MeliNotification, notice.notification_id)
        if existing is None:
            raise
        existing_job = await db.scalar(
            select(MeliSyncJob).where(MeliSyncJob.notification_id == existing.id)
        )
        return IngestResult(existing.id, existing_job.id if existing_job else None, True)
    return IngestResult(notification.id, job_id, False)
