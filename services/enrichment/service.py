#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: service.py
# NG-HEADER: Ubicación: services/enrichment/service.py
# NG-HEADER: Descripción: Gateway interno idempotente para crear y despachar jobs Enrich.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Punto de entrada compartido por API y procesos internos, sin llamadas HTTP."""

from __future__ import annotations

import os
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import CanonicalEnrichmentJob, CanonicalProduct


def enrichment_config_snapshot() -> dict:
    keys = (
        "ENRICH_AI_MODE", "ENRICH_OPENAI_MODEL", "ENRICH_OLLAMA_MODEL", "ENRICH_WEB_REQUIRED",
        "ENRICH_AUTO_APPLY_ENABLED", "ENRICH_AUTO_APPLY_MIN_CONFIDENCE", "ENRICH_TECHNICAL_MIN_CONFIDENCE",
        "ENRICH_MIN_INDEPENDENT_SOURCES", "ENRICH_MAX_SEARCH_RESULTS", "ENRICH_MAX_FETCH_SOURCES",
        "ENRICH_JOB_MAX_RETRIES", "ENRICH_JOB_TIME_LIMIT_MS",
    )
    return {key: os.getenv(key) for key in keys}


async def create_enrichment_job(
    session: AsyncSession, *, canonical_id: int, requested_product_id: int | None,
    client_request_id: str | None, scope: str, requested_by_user_id: int | None,
    batch_id: str | None = None,
) -> tuple[CanonicalEnrichmentJob, bool]:
    if not await session.get(CanonicalProduct, canonical_id):
        raise HTTPException(status_code=404, detail="Producto canónico no encontrado")
    request_key = client_request_id or uuid4().hex
    existing = await session.scalar(
        select(CanonicalEnrichmentJob).options(selectinload(CanonicalEnrichmentJob.sources)).where(
            CanonicalEnrichmentJob.client_request_id == request_key
        )
    )
    if existing:
        if existing.canonical_product_id != canonical_id or existing.scope != scope:
            raise HTTPException(status_code=409, detail="client_request_id ya fue usado con otro alcance")
        return existing, False
    job = CanonicalEnrichmentJob(
        id=uuid4().hex, canonical_product_id=canonical_id, requested_product_id=requested_product_id,
        client_request_id=request_key, batch_id=batch_id, scope=scope,
        requested_by_user_id=requested_by_user_id, config_snapshot=enrichment_config_snapshot(),
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        duplicate = await session.scalar(
            select(CanonicalEnrichmentJob).options(selectinload(CanonicalEnrichmentJob.sources)).where(
                CanonicalEnrichmentJob.client_request_id == request_key
            )
        )
        if duplicate:
            return duplicate, False
        raise HTTPException(status_code=409, detail={"code": "active_job_exists", "message": "El canónico ya tiene un job activo"}) from exc
    await session.refresh(job)
    return job, True


async def dispatch_enrichment_job(job: CanonicalEnrichmentJob, session: AsyncSession) -> None:
    if os.getenv("ENRICH_V2_ENABLED", "0") != "1":
        raise HTTPException(status_code=503, detail={"code": "enrich_v2_disabled"})
    try:
        from services.jobs.enrichment_jobs import process_canonical_enrichment
        if os.getenv("RUN_INLINE_JOBS", "0") == "1":
            from services.jobs.enrichment_jobs import process_canonical_enrichment_async
            await process_canonical_enrichment_async(job.id)
        else:
            process_canonical_enrichment.send(job.id)
    except HTTPException:
        raise
    except Exception as exc:
        job.status = "failed"
        job.error_code = "dispatch_failed"
        job.error_message = str(exc)[:1000]
        job.completed_at = datetime.utcnow()
        await session.commit()
        raise HTTPException(status_code=503, detail="No se pudo encolar el enriquecimiento") from exc
