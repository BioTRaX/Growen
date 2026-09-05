#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: jobs.py
# NG-HEADER: Ubicación: services/market/jobs.py
# NG-HEADER: Descripción: Creación idempotente y finalización de jobs persistentes de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Orquestación persistente de actualizaciones de Mercado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CanonicalProduct, MarketUpdateItem, MarketUpdateJob, MarketUpdateSourceResult


ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("partial", "succeeded", "failed", "cancelled")


@dataclass(frozen=True)
class EnqueueItem:
    product_id: int
    item_id: int | None
    job_id: str | None
    status: str
    deduplicated: bool


@dataclass(frozen=True)
class EnqueueResult:
    job: MarketUpdateJob | None
    items: list[EnqueueItem]


async def create_update_job(
    db: AsyncSession,
    product_ids: list[int],
    *,
    trigger: str,
    requested_by_user_id: int | None = None,
    correlation_id: str | None = None,
    force_rediscovery: bool = False,
    competitor_limit: int = 3,
    target_source_id: int | None = None,
) -> EnqueueResult:
    """Crea items sólo para productos sin trabajo activo y reporta deduplicados."""
    await expire_stale_items(db)
    unique_ids = list(dict.fromkeys(product_ids))
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        # Serializa pedidos concurrentes por producto sin bloquear otros SKUs.
        for product_id in sorted(unique_ids):
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:namespace, :product_id)"),
                {"namespace": 0x4D4B54, "product_id": product_id},
            )
    existing_products = set((await db.execute(
        select(CanonicalProduct.id).where(CanonicalProduct.id.in_(unique_ids))
    )).scalars())
    active = list((await db.execute(
        select(MarketUpdateItem)
        .where(MarketUpdateItem.product_id.in_(unique_ids), MarketUpdateItem.status.in_(ACTIVE_STATUSES))
        .order_by(MarketUpdateItem.created_at.desc())
    )).scalars())
    active_by_product = {item.product_id: item for item in active}

    new_product_ids = [product_id for product_id in unique_ids if product_id in existing_products and product_id not in active_by_product]
    job: MarketUpdateJob | None = None
    created: dict[int, MarketUpdateItem] = {}
    if new_product_ids:
        job = MarketUpdateJob(
            id=str(uuid4()),
            trigger=trigger,
            requested_by_user_id=requested_by_user_id,
            correlation_id=correlation_id,
            total_items=len(new_product_ids),
            config_snapshot={
                "currency": "ARS",
                "freshness_days": 7,
                "force_rediscovery": force_rediscovery,
                "competitor_limit": competitor_limit,
                **({
                    "target_source_id": target_source_id,
                    "force_price_detection": True,
                } if target_source_id is not None else {}),
            },
        )
        db.add(job)
        await db.flush()
        for product_id in new_product_ids:
            item = MarketUpdateItem(job_id=job.id, product_id=product_id)
            db.add(item)
            await db.flush()
            created[product_id] = item
        await db.commit()

    results: list[EnqueueItem] = []
    for product_id in unique_ids:
        if product_id not in existing_products:
            results.append(EnqueueItem(product_id, None, None, "not_found", False))
        elif product_id in active_by_product:
            item = active_by_product[product_id]
            results.append(EnqueueItem(product_id, item.id, item.job_id, item.status, True))
        else:
            item = created[product_id]
            results.append(EnqueueItem(product_id, item.id, item.job_id, "queued", False))
    return EnqueueResult(job, results)


async def claim_item(db: AsyncSession, item_id: int) -> MarketUpdateItem | None:
    item = await db.scalar(
        select(MarketUpdateItem).where(MarketUpdateItem.id == item_id).with_for_update()
    )
    if not item or item.status != "queued":
        return None
    item.status = "running"
    item.stage = "discovering"
    item.attempts += 1
    item.started_at = datetime.utcnow()
    job = await db.get(MarketUpdateJob, item.job_id)
    if job and job.status == "queued":
        job.status = "running"
        job.started_at = job.started_at or datetime.utcnow()
    await db.commit()
    return item


async def complete_item(
    db: AsyncSession,
    item_id: int,
    *,
    status: str,
    sources_total: int,
    sources_succeeded: int,
    sources_failed: int,
    market_price_reference,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"Estado terminal inválido: {status}")
    item = await db.get(MarketUpdateItem, item_id)
    if not item or item.status in TERMINAL_STATUSES:
        return
    item.status = status
    item.stage = "completed"
    item.sources_total = sources_total
    item.sources_succeeded = sources_succeeded
    item.sources_failed = sources_failed
    item.market_price_reference = market_price_reference
    item.error_code = error_code
    item.error_message = error_message[:1000] if error_message else None
    item.completed_at = datetime.utcnow()
    await db.flush()
    await finalize_job(db, item.job_id)
    await db.commit()


async def finalize_job(db: AsyncSession, job_id: str) -> None:
    job = await db.scalar(
        select(MarketUpdateJob).where(MarketUpdateJob.id == job_id).with_for_update()
    )
    if not job:
        return
    statuses = list((await db.execute(
        select(MarketUpdateItem.status).where(MarketUpdateItem.job_id == job_id)
    )).scalars())
    terminal = [status for status in statuses if status in TERMINAL_STATUSES]
    job.processed_items = len(terminal)
    job.success_count = sum(status == "succeeded" for status in statuses)
    job.error_count = sum(status == "failed" for status in statuses)
    if len(terminal) != len(statuses):
        job.status = "running"
        return
    if statuses and all(status == "succeeded" for status in statuses):
        job.status = "succeeded"
    elif statuses and all(status == "failed" for status in statuses):
        job.status = "failed"
    elif statuses and all(status == "cancelled" for status in statuses):
        job.status = "cancelled"
    else:
        job.status = "partial"
    job.completed_at = datetime.utcnow()


async def expire_stale_items(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    queued_timeout_seconds: int = 120,
    running_timeout_seconds: int = 360,
) -> int:
    """Finaliza leases vencidos y libera la deduplicación por producto."""
    current = now or datetime.utcnow()
    queued_cutoff = current - timedelta(seconds=queued_timeout_seconds)
    running_cutoff = current - timedelta(seconds=running_timeout_seconds)
    stale = list((await db.execute(
        select(MarketUpdateItem).where(
            ((MarketUpdateItem.status == "queued") & (MarketUpdateItem.created_at < queued_cutoff))
            | ((MarketUpdateItem.status == "running") & (MarketUpdateItem.started_at < running_cutoff))
        ).with_for_update()
    )).scalars())
    if not stale:
        return 0
    job_ids: set[str] = set()
    for item in stale:
        item.status = "failed"
        item.stage = "completed"
        item.error_code = "market_job_stalled"
        item.error_message = "El worker no completó el trabajo dentro del tiempo operativo"
        item.completed_at = current
        job_ids.add(item.job_id)
    await db.flush()
    for job_id in sorted(job_ids):
        await finalize_job(db, job_id)
    await db.commit()
    return len(stale)


async def job_payload(db: AsyncSession, job_id: str) -> dict | None:
    job = await db.get(MarketUpdateJob, job_id)
    if not job:
        return None
    items = list((await db.execute(
        select(MarketUpdateItem).where(MarketUpdateItem.job_id == job_id).order_by(MarketUpdateItem.id)
    )).scalars())
    item_ids = [item.id for item in items]
    source_results = list((await db.execute(
        select(MarketUpdateSourceResult)
        .where(MarketUpdateSourceResult.item_id.in_(item_ids))
        .order_by(MarketUpdateSourceResult.id)
    )).scalars()) if item_ids else []
    results_by_item: dict[int, list[dict]] = {item_id: [] for item_id in item_ids}
    for result in source_results:
        results_by_item[result.item_id].append({
            "id": result.id,
            "source_id": result.source_id,
            "operation": result.operation,
            "status": result.status,
            "attempt": result.attempt,
            "duration_ms": result.duration_ms,
            "http_status": result.http_status,
            "used_browser": result.used_browser,
            "observation_id": result.observation_id,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "retryable": result.retryable,
        })
    return {
        "id": job.id,
        "trigger": job.trigger,
        "status": job.status,
        "config_snapshot": job.config_snapshot or {},
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "success_count": job.success_count,
        "error_count": job.error_count,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "status": item.status,
                "stage": item.stage,
                "attempts": item.attempts,
                "competitors_existing": item.competitors_existing,
                "sources_discovered": item.sources_discovered,
                "sources_confirmed": item.sources_confirmed,
                "sources_quarantined": item.sources_quarantined,
                "sources_total": item.sources_total,
                "sources_succeeded": item.sources_succeeded,
                "sources_failed": item.sources_failed,
                "market_price_reference": float(item.market_price_reference) if item.market_price_reference is not None else None,
                "error_code": item.error_code,
                "error_message": item.error_message,
                "source_results": results_by_item[item.id],
            }
            for item in items
        ],
    }
