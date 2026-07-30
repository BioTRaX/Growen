#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: enrichment.py
# NG-HEADER: Ubicación: services/routers/enrichment.py
# NG-HEADER: Descripción: Contratos HTTP persistentes para Enrich v2 canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""API de investigación, propuestas y versiones de contenido canónico."""

from __future__ import annotations

import os
import hashlib
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CanonicalContentVersion,
    CanonicalEnrichmentJob,
    CanonicalProduct,
    ProductEquivalence,
    SupplierProduct,
)
from db.session import get_session
from services.auth import SessionData, current_session, require_csrf, require_roles


router = APIRouter(prefix="/canonical-products", tags=["enrichment"])

CONTENT_FIELDS = {
    "description_html",
    "weight_kg",
    "height_cm",
    "width_cm",
    "depth_cm",
    "technical_specs",
    "usage_instructions",
}


class EnrichmentJobCreate(BaseModel):
    client_request_id: str | None = Field(default=None, max_length=64)
    scope: Literal["full", "description", "technical"] = "full"
    requested_product_id: int | None = None


class EnrichmentApplyRequest(BaseModel):
    fields: list[str] = Field(min_length=1)
    expected_content_revision: int = Field(ge=0)


class EnrichmentRestoreRequest(BaseModel):
    expected_content_revision: int = Field(ge=0)


class EnrichmentBatchRequest(BaseModel):
    client_request_id: str | None = Field(default=None, max_length=64)
    product_ids: list[int] = Field(min_length=1, max_length=500)
    scope: Literal["full", "description", "technical"] = "full"


def canonical_snapshot(product: CanonicalProduct) -> dict:
    return {
        "description_html": product.description_html,
        "weight_kg": float(product.weight_kg) if product.weight_kg is not None else None,
        "height_cm": float(product.height_cm) if product.height_cm is not None else None,
        "width_cm": float(product.width_cm) if product.width_cm is not None else None,
        "depth_cm": float(product.depth_cm) if product.depth_cm is not None else None,
        "technical_specs": product.technical_specs or {},
        "usage_instructions": product.usage_instructions or {},
    }


def serialize_job(job: CanonicalEnrichmentJob) -> dict:
    result = job.result_json or {}
    return {
        "job_id": job.id,
        "canonical_product_id": job.canonical_product_id,
        "requested_product_id": job.requested_product_id,
        "status": job.status,
        "stage": job.stage,
        "scope": job.scope,
        "provider": job.provider,
        "model": job.model,
        "proposal": result.get("proposal"),
        "confidence": result.get("confidence"),
        "evidence_by_field": result.get("field_sources"),
        "sources": [
            {
                "url": source.url,
                "title": source.title,
                "source_type": source.source_type,
                "mime_type": source.mime_type,
                "content_hash": source.content_hash,
                "evidence": source.evidence_json,
            }
            for source in getattr(job, "sources", [])
        ],
        "applied_fields": job.applied_fields or [],
        "error": (
            {"code": job.error_code, "message": job.error_message}
            if job.error_code or job.error_message
            else None
        ),
        "attempts": job.attempts,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


async def resolve_canonical_id(session: AsyncSession, product_id: int) -> int | None:
    return await session.scalar(
        select(ProductEquivalence.canonical_product_id)
        .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
        .where(SupplierProduct.internal_product_id == product_id)
        .order_by(ProductEquivalence.id.asc())
        .limit(1)
    )


def enrichment_config_snapshot() -> dict:
    keys = (
        "ENRICH_AI_MODE",
        "ENRICH_OPENAI_MODEL",
        "ENRICH_OLLAMA_MODEL",
        "ENRICH_WEB_REQUIRED",
        "ENRICH_AUTO_APPLY_ENABLED",
        "ENRICH_AUTO_APPLY_MIN_CONFIDENCE",
        "ENRICH_TECHNICAL_MIN_CONFIDENCE",
        "ENRICH_MIN_INDEPENDENT_SOURCES",
        "ENRICH_MAX_SEARCH_RESULTS",
        "ENRICH_MAX_FETCH_SOURCES",
        "ENRICH_JOB_MAX_RETRIES",
        "ENRICH_JOB_TIME_LIMIT_MS",
    )
    return {key: os.getenv(key) for key in keys}


async def create_enrichment_job(
    session: AsyncSession,
    *,
    canonical_id: int,
    requested_product_id: int | None,
    client_request_id: str | None,
    scope: str,
    requested_by_user_id: int | None,
    batch_id: str | None = None,
) -> tuple[CanonicalEnrichmentJob, bool]:
    if not await session.get(CanonicalProduct, canonical_id):
        raise HTTPException(status_code=404, detail="Producto canónico no encontrado")
    request_key = client_request_id or uuid4().hex
    existing = await session.scalar(
        select(CanonicalEnrichmentJob)
        .options(selectinload(CanonicalEnrichmentJob.sources))
        .where(CanonicalEnrichmentJob.client_request_id == request_key)
    )
    if existing:
        if existing.canonical_product_id != canonical_id or existing.scope != scope:
            raise HTTPException(status_code=409, detail="client_request_id ya fue usado con otro alcance")
        return existing, False
    job = CanonicalEnrichmentJob(
        id=uuid4().hex,
        canonical_product_id=canonical_id,
        requested_product_id=requested_product_id,
        client_request_id=request_key,
        batch_id=batch_id,
        scope=scope,
        requested_by_user_id=requested_by_user_id,
        config_snapshot=enrichment_config_snapshot(),
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        duplicate = await session.scalar(
            select(CanonicalEnrichmentJob)
            .options(selectinload(CanonicalEnrichmentJob.sources))
            .where(CanonicalEnrichmentJob.client_request_id == request_key)
        )
        if duplicate:
            return duplicate, False
        raise HTTPException(
            status_code=409,
            detail={"code": "active_job_exists", "message": "El canónico ya tiene un job activo"},
        ) from exc
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


@router.post(
    "/{canonical_id}/enrichment-jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def start_enrichment_job(
    canonical_id: int,
    payload: EnrichmentJobCreate,
    session: AsyncSession = Depends(get_session),
    user: SessionData = Depends(current_session),
):
    job, created = await create_enrichment_job(
        session,
        canonical_id=canonical_id,
        requested_product_id=payload.requested_product_id,
        client_request_id=payload.client_request_id,
        scope=payload.scope,
        requested_by_user_id=user.user.id if user.user else None,
    )
    if created:
        await dispatch_enrichment_job(job, session)
    return {
        "job_id": job.id,
        "status": job.status,
        "status_url": f"/canonical-products/{canonical_id}/enrichment-jobs/{job.id}",
    }


@router.get(
    "/{canonical_id}/enrichment-jobs/{job_id}",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def get_enrichment_job(
    canonical_id: int,
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    job = await session.scalar(
        select(CanonicalEnrichmentJob)
        .options(selectinload(CanonicalEnrichmentJob.sources))
        .where(
            CanonicalEnrichmentJob.id == job_id,
            CanonicalEnrichmentJob.canonical_product_id == canonical_id,
        )
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return serialize_job(job)


@router.post(
    "/{canonical_id}/enrichment-jobs/{job_id}/apply",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def apply_enrichment_job(
    canonical_id: int,
    job_id: str,
    payload: EnrichmentApplyRequest,
    session: AsyncSession = Depends(get_session),
    user: SessionData = Depends(current_session),
):
    product = await session.get(CanonicalProduct, canonical_id, with_for_update=True)
    job = await session.get(CanonicalEnrichmentJob, job_id)
    if not product or not job or job.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Canónico o job no encontrado")
    if product.content_revision != payload.expected_content_revision:
        raise HTTPException(
            status_code=409,
            detail={"code": "content_revision_conflict", "current_revision": product.content_revision},
        )
    proposal = (job.result_json or {}).get("proposal") or {}
    selected = set(payload.fields)
    invalid = selected - CONTENT_FIELDS
    unavailable = selected - set(proposal)
    if invalid or unavailable:
        raise HTTPException(
            status_code=422,
            detail={"invalid_fields": sorted(invalid), "unavailable_fields": sorted(unavailable)},
        )
    for field in selected:
        setattr(product, field, proposal[field])
    product.content_revision += 1
    product.last_enriched_at = datetime.utcnow()
    product.enriched_by = user.user.id if user.user else None
    applied = set(job.applied_fields or []) | selected
    job.applied_fields = sorted(applied)
    remaining = (set(proposal) & CONTENT_FIELDS) - applied
    job.status = "partially_applied" if remaining else "applied"
    if not remaining:
        job.completed_at = datetime.utcnow()
    session.add(
        CanonicalContentVersion(
            canonical_product_id=canonical_id,
            origin="enrichment_apply",
            job_id=job.id,
            revision=product.content_revision,
            snapshot_json=canonical_snapshot(product),
            is_applied=True,
            created_by_user_id=user.user.id if user.user else None,
        )
    )
    await session.commit()
    return {
        "status": job.status,
        "applied_fields": job.applied_fields,
        "content_revision": product.content_revision,
    }


@router.post(
    "/{canonical_id}/enrichment-jobs/{job_id}/discard",
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def discard_enrichment_job(
    canonical_id: int,
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(CanonicalEnrichmentJob, job_id)
    if not job or job.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if job.status in {"applied", "failed", "cancelled", "discarded"}:
        raise HTTPException(status_code=409, detail="El job ya está en estado terminal")
    job.status = "discarded"
    job.completed_at = datetime.utcnow()
    await session.commit()
    return {"job_id": job.id, "status": job.status}


@router.get(
    "/{canonical_id}/content-versions",
    dependencies=[Depends(require_roles("colaborador", "admin"))],
)
async def list_content_versions(
    canonical_id: int,
    session: AsyncSession = Depends(get_session),
):
    versions = (
        await session.scalars(
            select(CanonicalContentVersion)
            .where(CanonicalContentVersion.canonical_product_id == canonical_id)
            .order_by(CanonicalContentVersion.created_at.desc(), CanonicalContentVersion.id.desc())
        )
    ).all()
    return [
        {
            "id": version.id,
            "origin": version.origin,
            "origin_product_id": version.origin_product_id,
            "job_id": version.job_id,
            "revision": version.revision,
            "snapshot": version.snapshot_json,
            "is_applied": version.is_applied,
            "created_by_user_id": version.created_by_user_id,
            "created_at": version.created_at.isoformat(),
        }
        for version in versions
    ]


@router.post(
    "/{canonical_id}/content-versions/{version_id}/restore",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def restore_content_version(
    canonical_id: int,
    version_id: int,
    payload: EnrichmentRestoreRequest,
    session: AsyncSession = Depends(get_session),
    user: SessionData = Depends(current_session),
):
    product = await session.get(CanonicalProduct, canonical_id, with_for_update=True)
    version = await session.get(CanonicalContentVersion, version_id)
    if not product or not version or version.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Canónico o versión no encontrada")
    if product.content_revision != payload.expected_content_revision:
        raise HTTPException(
            status_code=409,
            detail={"code": "content_revision_conflict", "current_revision": product.content_revision},
        )
    for field in CONTENT_FIELDS:
        if field in version.snapshot_json:
            setattr(product, field, version.snapshot_json[field])
    product.content_revision += 1
    product.last_enriched_at = datetime.utcnow()
    product.enriched_by = user.user.id if user.user else None
    session.add(
        CanonicalContentVersion(
            canonical_product_id=canonical_id,
            origin="restore",
            revision=product.content_revision,
            snapshot_json=canonical_snapshot(product),
            is_applied=True,
            created_by_user_id=user.user.id if user.user else None,
        )
    )
    await session.commit()
    return {"content_revision": product.content_revision, "restored_version_id": version_id}


@router.post(
    "/enrichment-batches",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf), Depends(require_roles("colaborador", "admin"))],
)
async def start_enrichment_batch(
    payload: EnrichmentBatchRequest,
    session: AsyncSession = Depends(get_session),
    user: SessionData = Depends(current_session),
):
    batch_id = payload.client_request_id or uuid4().hex
    resolved: dict[int, int] = {}
    skipped: list[dict] = []
    for product_id in dict.fromkeys(payload.product_ids):
        canonical_id = await resolve_canonical_id(session, product_id)
        if canonical_id is None:
            skipped.append({"product_id": product_id, "reason": "canonical_required"})
        else:
            resolved.setdefault(canonical_id, product_id)
    jobs: list[dict] = []
    for canonical_id, product_id in resolved.items():
        request_key = hashlib.sha256(f"{batch_id}:{canonical_id}".encode("utf-8")).hexdigest()
        job, created = await create_enrichment_job(
            session,
            canonical_id=canonical_id,
            requested_product_id=product_id,
            client_request_id=request_key,
            scope=payload.scope,
            requested_by_user_id=user.user.id if user.user else None,
            batch_id=batch_id,
        )
        dispatch_error = None
        if created:
            try:
                await dispatch_enrichment_job(job, session)
            except HTTPException as exc:
                dispatch_error = exc.detail
        jobs.append({
            "canonical_product_id": canonical_id,
            "product_id": product_id,
            "job_id": job.id,
            "status": job.status,
            "error": dispatch_error,
        })
    return {"batch_id": batch_id, "jobs": jobs, "skipped": skipped}
