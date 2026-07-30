#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: service.py
# NG-HEADER: Ubicación: services/knowledge/service.py
# NG-HEADER: Descripción: Reglas transaccionales, confianza y serialización de conocimiento canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Reglas de dominio para activos de conocimiento canónico."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    CanonicalKnowledgeAsset,
    CanonicalKnowledgeAssetCapability,
    CanonicalKnowledgeEvent,
    CanonicalKnowledgeLabel,
    CanonicalKnowledgeLocation,
    CanonicalKnowledgeMarketProfile,
    CanonicalProduct,
    KnowledgeCapability,
)


LABELS = {"manufacturer", "supplier", "market", "manual", "catalog", "msds", "official", "other"}
DEFAULT_CAPABILITIES = {
    "manufacturer": {"description", "technical_specs", "compatibility", "images", "manuals", "warranty", "certifications"},
    "supplier": {"description", "compatibility", "images", "availability", "offers"},
    "market": {"price", "availability", "offers"},
    "manual": {"technical_specs", "compatibility", "manuals", "warranty", "certifications"},
    "catalog": {"description", "technical_specs", "images"},
    "msds": {"technical_specs", "certifications"},
}
AUTHORITY = {
    "manufacturer": 100.0,
    "official": 96.0,
    "supplier": 90.0,
    "manual": 92.0,
    "catalog": 82.0,
    "msds": 95.0,
    "market": 72.0,
    "other": 35.0,
}


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="La URL debe ser HTTP/HTTPS y contener un dominio")
    host = parsed.hostname.lower()
    port = parsed.port
    authority = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), authority, path.rstrip("/") or "/", parsed.query, ""))


def deterministic_trust(labels: set[str], *, validated: bool = False, fresh: bool = False, agreement: float = 0.5, extraction_success: float = 0.5) -> tuple[float, dict]:
    authority = max((AUTHORITY.get(label, 35.0) for label in labels), default=0.0)
    validation = 100.0 if validated else 50.0
    freshness = 100.0 if fresh else 50.0
    agreement_score = max(0.0, min(1.0, agreement)) * 100
    extraction = max(0.0, min(1.0, extraction_success)) * 100
    score = round(
        authority * 0.40
        + validation * 0.20
        + freshness * 0.15
        + agreement_score * 0.15
        + extraction * 0.10,
        2,
    )
    return score, {
        "authority": authority,
        "validation": validation,
        "freshness": freshness,
        "agreement": agreement_score,
        "extraction_success": extraction,
        "weights": {"authority": 0.40, "validation": 0.20, "freshness": 0.15, "agreement": 0.15, "extraction_success": 0.10},
    }


def apply_ai_adjustment(asset: CanonicalKnowledgeAsset, adjustment: float | None, reason: dict | None) -> None:
    bounded = None if adjustment is None else max(-10.0, min(10.0, float(adjustment)))
    asset.ai_trust_adjustment = bounded
    asset.ai_trust_reason = reason
    deterministic = float((asset.trust_breakdown or {}).get("deterministic", asset.trust_score))
    asset.trust_score = round(max(0.0, min(100.0, deterministic + (bounded or 0))), 2)


def _options():
    return (
        selectinload(CanonicalKnowledgeAsset.locations),
        selectinload(CanonicalKnowledgeAsset.labels),
        selectinload(CanonicalKnowledgeAsset.capabilities),
        selectinload(CanonicalKnowledgeAsset.market_profile),
    )


async def get_asset(session: AsyncSession, asset_id: int) -> CanonicalKnowledgeAsset:
    asset = await session.scalar(select(CanonicalKnowledgeAsset).options(*_options()).where(CanonicalKnowledgeAsset.id == asset_id))
    if not asset:
        raise HTTPException(status_code=404, detail="Activo de conocimiento no encontrado")
    return asset


async def list_assets(session: AsyncSession, canonical_product_id: int, *, include_archived: bool = False) -> list[CanonicalKnowledgeAsset]:
    if not await session.get(CanonicalProduct, canonical_product_id):
        raise HTTPException(status_code=404, detail="Producto canónico no encontrado")
    stmt = select(CanonicalKnowledgeAsset).options(*_options()).where(
        CanonicalKnowledgeAsset.canonical_product_id == canonical_product_id
    )
    if not include_archived:
        stmt = stmt.where(CanonicalKnowledgeAsset.status != "archived")
    return list((await session.scalars(stmt.order_by(CanonicalKnowledgeAsset.trust_score.desc(), CanonicalKnowledgeAsset.id))).unique())


async def _sync_market_profile(asset: CanonicalKnowledgeAsset) -> None:
    labels = {item.label for item in asset.labels}
    if "market" in labels:
        if not asset.market_profile:
            asset.market_profile = CanonicalKnowledgeMarketProfile(
                source_type="static",
                currency="ARS",
                is_active=False,
                validation_status="warning",
            )
    elif asset.market_profile:
        asset.market_profile.is_active = False


async def create_asset(
    session: AsyncSession,
    *,
    canonical_product_id: int,
    title: str,
    asset_type: str,
    labels: set[str],
    capabilities: set[str] | None,
    url: str | None,
    exclude_from_enrichment: bool,
    status: str,
    origin: str,
    user_id: int | None,
) -> CanonicalKnowledgeAsset:
    if not await session.get(CanonicalProduct, canonical_product_id):
        raise HTTPException(status_code=404, detail="Producto canónico no encontrado")
    invalid = labels - LABELS
    if invalid:
        raise HTTPException(status_code=422, detail=f"Etiquetas inválidas: {sorted(invalid)}")
    normalized = normalize_url(url)
    if normalized:
        existing = await session.scalar(
            select(CanonicalKnowledgeAsset)
            .join(CanonicalKnowledgeLocation)
            .where(
                CanonicalKnowledgeAsset.canonical_product_id == canonical_product_id,
                CanonicalKnowledgeLocation.normalized_url == normalized,
                CanonicalKnowledgeAsset.status != "archived",
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="La URL ya pertenece a un activo del producto")
    selected_capabilities = set(capabilities or set())
    if not selected_capabilities:
        for label in labels:
            selected_capabilities.update(DEFAULT_CAPABILITIES.get(label, set()))
    valid_capabilities = set(await session.scalars(select(KnowledgeCapability.code).where(KnowledgeCapability.is_active.is_(True))))
    if selected_capabilities - valid_capabilities:
        raise HTTPException(status_code=422, detail="Se enviaron capacidades inexistentes o inactivas")
    score, breakdown = deterministic_trust(labels)
    breakdown["deterministic"] = score
    asset = CanonicalKnowledgeAsset(
        canonical_product_id=canonical_product_id,
        title=title.strip(),
        asset_type=asset_type,
        status=status,
        origin=origin,
        exclude_from_enrichment=exclude_from_enrichment,
        trust_score=score,
        trust_breakdown=breakdown,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    asset.labels = [CanonicalKnowledgeLabel(label=label) for label in sorted(labels)]
    asset.capabilities = [
        CanonicalKnowledgeAssetCapability(capability_code=code, origin=origin, confidence=score / 100)
        for code in sorted(selected_capabilities)
    ]
    if normalized:
        asset.locations.append(CanonicalKnowledgeLocation(url=url, normalized_url=normalized, status="pending", is_primary=True))
    await _sync_market_profile(asset)
    session.add(asset)
    await session.flush()
    session.add(CanonicalKnowledgeEvent(
        canonical_product_id=canonical_product_id,
        asset_id=asset.id,
        event_type="asset_created",
        actor_user_id=user_id,
        payload_json={"labels": sorted(labels), "capabilities": sorted(selected_capabilities), "origin": origin},
    ))
    await session.commit()
    return await get_asset(session, asset.id)


async def update_asset(
    session: AsyncSession,
    asset: CanonicalKnowledgeAsset,
    *,
    expected_revision: int,
    title: str | None,
    labels: set[str] | None,
    capabilities: set[str] | None,
    exclude_from_enrichment: bool | None,
    market_is_active: bool | None,
    market_is_mandatory: bool | None,
    market_source_type: str | None,
    market_argentina_delivery_confirmed: bool | None,
    user_id: int | None,
) -> CanonicalKnowledgeAsset:
    if asset.revision != expected_revision:
        raise HTTPException(status_code=409, detail="El conocimiento cambió; recargue antes de guardar")
    if labels is not None:
        invalid = labels - LABELS
        if invalid or not labels:
            raise HTTPException(status_code=422, detail="Debe conservar al menos una etiqueta válida")
        asset.labels = [CanonicalKnowledgeLabel(label=label) for label in sorted(labels)]
    if capabilities is not None:
        valid = set(await session.scalars(select(KnowledgeCapability.code).where(KnowledgeCapability.is_active.is_(True))))
        if capabilities - valid:
            raise HTTPException(status_code=422, detail="Se enviaron capacidades inexistentes o inactivas")
        asset.capabilities = [
            CanonicalKnowledgeAssetCapability(capability_code=code, origin="manual", confidence=asset.trust_score / 100)
            for code in sorted(capabilities)
        ]
    if title is not None:
        asset.title = title.strip()
    if exclude_from_enrichment is not None:
        asset.exclude_from_enrichment = exclude_from_enrichment
    await _sync_market_profile(asset)
    has_market_label = any(item.label == "market" for item in asset.labels)
    if asset.market_profile and has_market_label:
        profile = asset.market_profile
        if market_is_active is not None:
            profile.is_active = market_is_active
        if market_is_mandatory is not None:
            profile.is_mandatory = market_is_mandatory
        if market_source_type is not None:
            profile.source_type = market_source_type
        if market_argentina_delivery_confirmed is not None:
            profile.currency = "ARS"
            profile.ars_confirmed = True
            profile.argentina_delivery_confirmed = market_argentina_delivery_confirmed
            profile.validation_status = "verified" if market_argentina_delivery_confirmed else "warning"
            profile.validation_detail = {
                "reason": "manual_knowledge_configuration",
                "delivery_attested": market_argentina_delivery_confirmed,
            }
    asset.updated_by_user_id = user_id
    asset.revision += 1
    score, breakdown = deterministic_trust(
        {item.label for item in asset.labels},
        validated=bool(
            has_market_label
            and asset.market_profile
            and asset.market_profile.validation_status == "verified"
        ),
    )
    breakdown["deterministic"] = score
    asset.trust_score = score
    asset.trust_breakdown = breakdown
    apply_ai_adjustment(asset, asset.ai_trust_adjustment, asset.ai_trust_reason)
    session.add(CanonicalKnowledgeEvent(
        canonical_product_id=asset.canonical_product_id,
        asset_id=asset.id,
        event_type="asset_updated",
        actor_user_id=user_id,
        payload_json={
            "revision": asset.revision,
            "market_delivery_attested": market_argentina_delivery_confirmed,
        },
    ))
    await session.commit()
    return await get_asset(session, asset.id)


async def archive_asset(session: AsyncSession, asset: CanonicalKnowledgeAsset, user_id: int | None) -> None:
    profile = asset.__dict__.get("market_profile")
    if profile is None:
        profile = await session.scalar(
            select(CanonicalKnowledgeMarketProfile).where(
                CanonicalKnowledgeMarketProfile.asset_id == asset.id
            )
        )
    asset.status = "archived"
    asset.archived_at = datetime.utcnow()
    asset.exclude_from_enrichment = True
    asset.revision += 1
    if profile:
        profile.is_active = False
    session.add(CanonicalKnowledgeEvent(
        canonical_product_id=asset.canonical_product_id,
        asset_id=asset.id,
        event_type="asset_archived",
        actor_user_id=user_id,
    ))
    await session.commit()


async def restore_asset(session: AsyncSession, asset: CanonicalKnowledgeAsset, user_id: int | None) -> CanonicalKnowledgeAsset:
    asset.status = "confirmed" if asset.labels else "pending"
    asset.archived_at = None
    asset.revision += 1
    session.add(CanonicalKnowledgeEvent(
        canonical_product_id=asset.canonical_product_id,
        asset_id=asset.id,
        event_type="asset_restored",
        actor_user_id=user_id,
    ))
    await session.commit()
    return await get_asset(session, asset.id)


async def register_discovered_asset(
    session: AsyncSession,
    *,
    canonical_product_id: int,
    title: str,
    url: str,
    labels: set[str] | None = None,
    classification_confidence: float = 0,
) -> CanonicalKnowledgeAsset:
    normalized = normalize_url(url)
    existing = await session.scalar(
        select(CanonicalKnowledgeAsset)
        .options(*_options())
        .join(CanonicalKnowledgeLocation)
        .where(
            CanonicalKnowledgeAsset.canonical_product_id == canonical_product_id,
            CanonicalKnowledgeLocation.normalized_url == normalized,
        )
    )
    if existing:
        return existing
    confirmed = classification_confidence >= 0.90 and bool(labels)
    return await create_asset(
        session,
        canonical_product_id=canonical_product_id,
        title=title or normalized or "Fuente descubierta",
        asset_type="web",
        labels=set(labels or set()) if confirmed else set(),
        capabilities=None,
        url=url,
        exclude_from_enrichment=not confirmed,
        status="confirmed" if confirmed else "pending",
        origin="enrichment_auto",
        user_id=None,
    )


def serialize_asset(asset: CanonicalKnowledgeAsset) -> dict:
    labels = sorted(item.label for item in asset.labels)
    capabilities = sorted(item.capability_code for item in asset.capabilities if item.enabled)
    profile = asset.market_profile
    return {
        "id": asset.id,
        "canonical_product_id": asset.canonical_product_id,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "status": asset.status,
        "origin": asset.origin,
        "labels": labels,
        "capabilities": capabilities,
        "exclude_from_enrichment": asset.exclude_from_enrichment,
        "trust_score": asset.trust_score,
        "trust_breakdown": asset.trust_breakdown,
        "ai_trust_adjustment": asset.ai_trust_adjustment,
        "ai_trust_reason": asset.ai_trust_reason,
        "revision": asset.revision,
        "archived_at": asset.archived_at.isoformat() if asset.archived_at else None,
        "locations": [
            {
                "id": location.id,
                "url": location.url,
                "storage_path": location.storage_path,
                "mime_type": location.mime_type,
                "content_hash": location.content_hash,
                "content_version": location.content_version,
                "status": location.status,
                "is_primary": location.is_primary,
                "metadata": location.metadata_json,
                "last_fetched_at": location.last_fetched_at.isoformat() if location.last_fetched_at else None,
                "error": location.last_error_message,
            }
            for location in asset.locations
        ],
        "market": None if not profile else {
            "id": profile.id,
            "last_price": float(profile.last_price) if profile.last_price is not None else None,
            "last_checked_at": profile.last_checked_at.isoformat() if profile.last_checked_at else None,
            "is_mandatory": profile.is_mandatory,
            "is_active": profile.is_active,
            "validation_status": profile.validation_status,
            "ars_confirmed": profile.ars_confirmed,
            "argentina_delivery_confirmed": profile.argentina_delivery_confirmed,
            "currency": profile.currency,
            "source_type": profile.source_type,
        },
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


async def knowledge_summary(session: AsyncSession, canonical_product_id: int) -> dict:
    assets = await list_assets(session, canonical_product_id, include_archived=True)
    return {
        "total": len(assets),
        "confirmed": sum(item.status == "confirmed" for item in assets),
        "pending": sum(item.status == "pending" for item in assets),
        "archived": sum(item.status == "archived" for item in assets),
        "by_type": {
            kind: sum(item.asset_type == kind for item in assets)
            for kind in ("web", "document", "image", "video")
        },
    }
