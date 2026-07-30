#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: canonical_knowledge.py
# NG-HEADER: Ubicación: services/routers/canonical_knowledge.py
# NG-HEADER: Descripción: API del Centro de Conocimiento del Producto Canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Contratos HTTP para conocimiento reusable por producto canónico."""

from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CanonicalKnowledgeEvent,
    CanonicalKnowledgeFact,
    CanonicalKnowledgeJob,
    CanonicalKnowledgeLocation,
    CanonicalKnowledgeAsset,
    KnowledgeCapability,
)
from db.session import get_session
from services.auth import SessionData, current_session, require_csrf, require_roles
from services.knowledge.service import (
    LABELS,
    archive_asset,
    create_asset,
    get_asset,
    knowledge_summary,
    list_assets,
    normalize_url,
    restore_asset,
    serialize_asset,
    update_asset,
)
from services.media import get_media_root, sha256_of_file


router = APIRouter(prefix="/canonical-products", tags=["canonical-knowledge"])
capabilities_router = APIRouter(prefix="/knowledge-capabilities", tags=["canonical-knowledge"])
staff = Depends(require_roles("colaborador", "admin"))


class KnowledgeAssetCreate(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    asset_type: Literal["web", "document", "image", "video"] = "web"
    url: str | None = Field(default=None, max_length=2000)
    labels: set[str] = Field(default_factory=set)
    capabilities: set[str] = Field(default_factory=set)
    exclude_from_enrichment: bool = False
    market_is_active: bool = True
    market_is_mandatory: bool = False
    market_source_type: Literal["static", "dynamic"] = "static"
    market_argentina_delivery_confirmed: bool = False


class KnowledgeAssetPatch(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=2, max_length=500)
    labels: set[str] | None = None
    capabilities: set[str] | None = None
    exclude_from_enrichment: bool | None = None
    market_is_active: bool | None = None
    market_is_mandatory: bool | None = None
    market_source_type: Literal["static", "dynamic"] | None = None
    market_argentina_delivery_confirmed: bool | None = None


class KnowledgeLocationCreate(BaseModel):
    url: str = Field(max_length=2000)
    is_primary: bool = False


class KnowledgeCapabilityCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class KnowledgeCapabilityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class KnowledgeTrustOverride(BaseModel):
    expected_revision: int = Field(ge=1)
    score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=500)


async def _queue_processing(
    db: AsyncSession,
    asset: CanonicalKnowledgeAsset,
    requested_by_user_id: int | None,
) -> dict:
    active = await db.scalar(select(CanonicalKnowledgeJob).where(
        CanonicalKnowledgeJob.asset_id == asset.id,
        CanonicalKnowledgeJob.status.in_(("queued", "running")),
    ))
    if active:
        return {"job_id": active.id, "status": active.status, "deduplicated": True}
    job = CanonicalKnowledgeJob(
        id=uuid4().hex,
        canonical_product_id=asset.canonical_product_id,
        asset_id=asset.id,
        requested_by_user_id=requested_by_user_id,
    )
    db.add(job)
    await db.commit()
    from services.jobs.knowledge_jobs import process_knowledge
    message = process_knowledge.send(job.id)
    return {"job_id": job.id, "status": "queued", "message_id": message.message_id, "deduplicated": False}


@router.get("/{canonical_id}/knowledge", dependencies=[staff])
async def get_knowledge(
    canonical_id: int,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_session),
):
    assets = await list_assets(db, canonical_id, include_archived=include_archived)
    return {
        "canonical_product_id": canonical_id,
        "summary": await knowledge_summary(db, canonical_id),
        "items": [serialize_asset(item) for item in assets],
    }


@router.post(
    "/{canonical_id}/knowledge",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf), staff],
)
async def add_knowledge(
    canonical_id: int,
    payload: KnowledgeAssetCreate,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    if not payload.labels:
        raise HTTPException(status_code=422, detail="Las altas manuales requieren al menos una etiqueta")
    asset = await create_asset(
        db,
        canonical_product_id=canonical_id,
        title=payload.title,
        asset_type=payload.asset_type,
        labels=set(payload.labels),
        capabilities=set(payload.capabilities),
        url=payload.url,
        exclude_from_enrichment=payload.exclude_from_enrichment,
        status="confirmed",
        origin="manual",
        user_id=session_data.user.id if session_data.user else None,
    )
    if asset.market_profile:
        asset = await update_asset(
            db,
            asset,
            expected_revision=asset.revision,
            title=None,
            labels=None,
            capabilities=None,
            exclude_from_enrichment=None,
            market_is_active=payload.market_is_active,
            market_is_mandatory=payload.market_is_mandatory,
            market_source_type=payload.market_source_type,
            market_argentina_delivery_confirmed=payload.market_argentina_delivery_confirmed,
            user_id=session_data.user.id if session_data.user else None,
        )
    return serialize_asset(asset)


@router.get("/{canonical_id}/knowledge/{asset_id:int}", dependencies=[staff])
async def get_knowledge_asset(canonical_id: int, asset_id: int, db: AsyncSession = Depends(get_session)):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    return serialize_asset(asset)


@router.patch(
    "/{canonical_id}/knowledge/{asset_id:int}",
    dependencies=[Depends(require_csrf), staff],
)
async def patch_knowledge_asset(
    canonical_id: int,
    asset_id: int,
    payload: KnowledgeAssetPatch,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    updated = await update_asset(
        db,
        asset,
        expected_revision=payload.expected_revision,
        title=payload.title,
        labels=set(payload.labels) if payload.labels is not None else None,
        capabilities=set(payload.capabilities) if payload.capabilities is not None else None,
        exclude_from_enrichment=payload.exclude_from_enrichment,
        market_is_active=payload.market_is_active,
        market_is_mandatory=payload.market_is_mandatory,
        market_source_type=payload.market_source_type,
        market_argentina_delivery_confirmed=payload.market_argentina_delivery_confirmed,
        user_id=session_data.user.id if session_data.user else None,
    )
    return serialize_asset(updated)


@router.delete(
    "/{canonical_id}/knowledge/{asset_id:int}",
    status_code=204,
    dependencies=[Depends(require_csrf), staff],
)
async def delete_knowledge_asset(
    canonical_id: int,
    asset_id: int,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    await archive_asset(db, asset, session_data.user.id if session_data.user else None)


@router.post(
    "/{canonical_id}/knowledge/{asset_id:int}/restore",
    dependencies=[Depends(require_csrf), staff],
)
async def restore_knowledge_asset(
    canonical_id: int,
    asset_id: int,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    return serialize_asset(await restore_asset(db, asset, session_data.user.id if session_data.user else None))


@router.post(
    "/{canonical_id}/knowledge/{asset_id:int}/locations",
    status_code=201,
    dependencies=[Depends(require_csrf), staff],
)
async def add_location(
    canonical_id: int,
    asset_id: int,
    payload: KnowledgeLocationCreate,
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    normalized = normalize_url(payload.url)
    if any(item.normalized_url == normalized for item in asset.locations):
        raise HTTPException(status_code=409, detail="La ubicación ya existe")
    if payload.is_primary:
        for item in asset.locations:
            item.is_primary = False
    location = CanonicalKnowledgeLocation(
        asset_id=asset.id,
        url=payload.url,
        normalized_url=normalized,
        status="pending",
        is_primary=payload.is_primary or not asset.locations,
    )
    db.add(location)
    asset.revision += 1
    await db.commit()
    return serialize_asset(await get_asset(db, asset.id))


@router.post(
    "/{canonical_id}/knowledge/upload",
    status_code=201,
    dependencies=[Depends(require_csrf), staff],
)
async def upload_knowledge(
    canonical_id: int,
    title: str,
    labels: str = "manual",
    capabilities: str = "manuals,technical_specs",
    file: UploadFile = File(...),
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    allowed_mime = {
        "application/pdf": "document",
        "image/jpeg": "image",
        "image/png": "image",
        "image/webp": "image",
        "video/mp4": "video",
        "video/webm": "video",
    }
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0]
    if mime not in allowed_mime:
        raise HTTPException(status_code=415, detail="MIME no admitido para conocimiento canónico")
    max_bytes = 100 * 1024 * 1024 if allowed_mime[mime] == "video" else 20 * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="El archivo supera el límite configurado")
    digest = __import__("hashlib").sha256(data).hexdigest()
    duplicate = await db.scalar(
        select(CanonicalKnowledgeAsset)
        .join(CanonicalKnowledgeLocation)
        .where(
            CanonicalKnowledgeAsset.canonical_product_id == canonical_id,
            CanonicalKnowledgeLocation.content_hash == digest,
            CanonicalKnowledgeAsset.status != "archived",
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={"message": "El archivo ya pertenece a la base de conocimiento", "asset_id": duplicate.id},
        )
    root = get_media_root() / "canonical-knowledge" / str(canonical_id) / digest[:2]
    root.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    target = root / f"{digest}{suffix}"
    if not target.exists():
        target.write_bytes(data)
    asset = await create_asset(
        db,
        canonical_product_id=canonical_id,
        title=title,
        asset_type=allowed_mime[mime],
        labels={item.strip() for item in labels.split(",") if item.strip()},
        capabilities={item.strip() for item in capabilities.split(",") if item.strip()},
        url=None,
        exclude_from_enrichment=False,
        status="confirmed",
        origin="upload",
        user_id=session_data.user.id if session_data.user else None,
    )
    asset.locations.append(CanonicalKnowledgeLocation(
        storage_path=str(target.relative_to(get_media_root())).replace("\\", "/"),
        mime_type=mime,
        content_hash=digest,
        status="pending",
        is_primary=True,
    ))
    await db.commit()
    return serialize_asset(await get_asset(db, asset.id))


@router.post(
    "/{canonical_id}/knowledge/{asset_id:int}/process",
    status_code=202,
    dependencies=[Depends(require_csrf), staff],
)
async def process_knowledge_asset(
    canonical_id: int,
    asset_id: int,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    return await _queue_processing(
        db,
        asset,
        session_data.user.id if session_data.user else None,
    )


@router.post(
    "/{canonical_id}/knowledge/{asset_id:int}/revalidate",
    status_code=202,
    dependencies=[Depends(require_csrf), staff],
)
async def revalidate_knowledge_asset(
    canonical_id: int,
    asset_id: int,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    for location in asset.locations:
        location.status = "stale"
        location.expires_at = datetime.utcnow()
    asset.revision += 1
    db.add(CanonicalKnowledgeEvent(
        canonical_product_id=canonical_id,
        asset_id=asset.id,
        event_type="asset_revalidation_requested",
        actor_user_id=session_data.user.id if session_data.user else None,
    ))
    await db.commit()
    return await _queue_processing(
        db,
        asset,
        session_data.user.id if session_data.user else None,
    )


@router.post(
    "/{canonical_id}/knowledge/{asset_id:int}/trust",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def override_knowledge_trust(
    canonical_id: int,
    asset_id: int,
    payload: KnowledgeTrustOverride,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    asset = await get_asset(db, asset_id)
    if asset.canonical_product_id != canonical_id:
        raise HTTPException(status_code=404, detail="Activo no encontrado para el producto")
    if asset.revision != payload.expected_revision:
        raise HTTPException(status_code=409, detail="El conocimiento cambió; recargue antes de guardar")
    previous = asset.trust_score
    asset.trust_score = payload.score
    breakdown = dict(asset.trust_breakdown or {})
    breakdown["manual_override"] = {
        "score": payload.score,
        "reason": payload.reason,
        "user_id": session_data.user.id if session_data.user else None,
        "at": datetime.utcnow().isoformat(),
    }
    asset.trust_breakdown = breakdown
    asset.revision += 1
    db.add(CanonicalKnowledgeEvent(
        canonical_product_id=canonical_id,
        asset_id=asset.id,
        event_type="trust_overridden",
        actor_user_id=session_data.user.id if session_data.user else None,
        payload_json={"previous": previous, "score": payload.score, "reason": payload.reason},
    ))
    await db.commit()
    return serialize_asset(await get_asset(db, asset.id))


@router.get("/{canonical_id}/knowledge/jobs", dependencies=[staff])
async def list_knowledge_jobs(canonical_id: int, db: AsyncSession = Depends(get_session)):
    rows = await db.scalars(select(CanonicalKnowledgeJob).where(
        CanonicalKnowledgeJob.canonical_product_id == canonical_id
    ).order_by(CanonicalKnowledgeJob.created_at.desc()).limit(100))
    return {"items": [{
        "id": item.id,
        "asset_id": item.asset_id,
        "status": item.status,
        "stage": item.stage,
        "result": item.result_json,
        "error": item.error_message,
        "created_at": item.created_at.isoformat(),
    } for item in rows]}


@router.get("/{canonical_id}/knowledge/facts", dependencies=[staff])
async def list_knowledge_facts(canonical_id: int, db: AsyncSession = Depends(get_session)):
    rows = await db.scalars(select(CanonicalKnowledgeFact).where(
        CanonicalKnowledgeFact.canonical_product_id == canonical_id
    ).order_by(CanonicalKnowledgeFact.fact_key))
    return {"items": [{
        "id": item.id,
        "fact_key": item.fact_key,
        "capability": item.capability_code,
        "value": item.value_json,
        "confidence": item.confidence,
        "status": item.status,
        "supporting_claim_ids": item.supporting_claim_ids,
        "revision": item.revision,
    } for item in rows]}


@router.get("/{canonical_id}/knowledge/history", dependencies=[staff])
async def list_knowledge_history(canonical_id: int, db: AsyncSession = Depends(get_session)):
    rows = await db.scalars(select(CanonicalKnowledgeEvent).where(
        CanonicalKnowledgeEvent.canonical_product_id == canonical_id
    ).order_by(CanonicalKnowledgeEvent.created_at.desc()).limit(200))
    return {"items": [{
        "id": item.id,
        "asset_id": item.asset_id,
        "event_type": item.event_type,
        "actor_user_id": item.actor_user_id,
        "payload": item.payload_json,
        "created_at": item.created_at.isoformat(),
    } for item in rows]}


@capabilities_router.get("", dependencies=[staff])
async def list_capabilities(db: AsyncSession = Depends(get_session)):
    rows = await db.scalars(select(KnowledgeCapability).order_by(KnowledgeCapability.code))
    return {"items": [{"code": item.code, "name": item.name, "description": item.description, "is_active": item.is_active} for item in rows]}


@capabilities_router.post(
    "",
    status_code=201,
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_capability(payload: KnowledgeCapabilityCreate, db: AsyncSession = Depends(get_session)):
    if await db.get(KnowledgeCapability, payload.code):
        raise HTTPException(status_code=409, detail="La capacidad ya existe")
    capability = KnowledgeCapability(code=payload.code, name=payload.name, description=payload.description)
    db.add(capability)
    await db.commit()
    return {"code": capability.code, "name": capability.name, "description": capability.description, "is_active": True}


@capabilities_router.patch(
    "/{code}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def patch_capability(
    code: str,
    payload: KnowledgeCapabilityPatch,
    db: AsyncSession = Depends(get_session),
):
    capability = await db.get(KnowledgeCapability, code)
    if not capability:
        raise HTTPException(status_code=404, detail="Capacidad no encontrada")
    if payload.name is not None:
        capability.name = payload.name
    if payload.description is not None:
        capability.description = payload.description
    if payload.is_active is not None:
        capability.is_active = payload.is_active
    await db.commit()
    return {
        "code": capability.code,
        "name": capability.name,
        "description": capability.description,
        "is_active": capability.is_active,
    }


@capabilities_router.delete(
    "/{code}",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def delete_capability(code: str, db: AsyncSession = Depends(get_session)):
    capability = await db.get(KnowledgeCapability, code)
    if not capability:
        raise HTTPException(status_code=404, detail="Capacidad no encontrada")
    capability.is_active = False
    await db.commit()
