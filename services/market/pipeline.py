#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: pipeline.py
# NG-HEADER: Ubicación: services/market/pipeline.py
# NG-HEADER: Descripción: Selección de competidores y orquestación del pipeline automático de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Reglas puras compartidas por API y worker para diversidad de competidores."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import CanonicalKnowledgeAsset, CanonicalProduct, MarketSource, MarketUpdateItem
from services.knowledge.service import create_asset
from services.market.source_validation import validate_public_url


_DOMAIN_ALIASES = {
    "mercadolibre.com": "mercadolibre.com.ar",
    "mercadolibre.com.ar": "mercadolibre.com.ar",
    "mlstatic.com": "mercadolibre.com.ar",
}


def competitor_key(url: str) -> str:
    """Normaliza una URL a una identidad estable de competidor."""
    hostname = (urlparse(url).hostname or "").lower().strip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    for domain, alias in _DOMAIN_ALIASES.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return alias
    return hostname


def select_missing_competitors(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_urls: Iterable[str],
    archived_urls: Iterable[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Selecciona candidatos de dominios nuevos sin superar la cobertura objetivo."""
    existing = {competitor_key(url) for url in existing_urls if competitor_key(url)}
    blocked = {competitor_key(url) for url in archived_urls if competitor_key(url)}
    remaining = max(0, limit - len(existing))
    if remaining == 0:
        return []
    selected: list[dict[str, Any]] = []
    seen = set(existing) | blocked
    for candidate in candidates:
        key = competitor_key(str(candidate.get("url") or ""))
        if not key or key in seen:
            continue
        selected.append(candidate)
        seen.add(key)
        if len(selected) >= remaining:
            break
    return selected


def has_argentina_delivery_evidence(url: str, snippet: str) -> bool:
    """Acepta sólo evidencia textual explícita de entrega en Argentina."""
    text = snippet.lower()
    if re.search(r"\bargentina\b", text):
        return True
    hostname = (urlparse(url).hostname or "").lower()
    domestic_delivery = re.search(r"\b(env[ií]os?|entregas?)\b.*\b(todo el pa[ií]s|nacional)\b", text)
    return hostname.endswith(".ar") and bool(domestic_delivery)


@dataclass(frozen=True)
class DiscoveryOutcome:
    candidates: list[MarketSource]
    error_code: str | None = None
    error_message: str | None = None


async def _product_market_sources(db: AsyncSession, product_id: int) -> list[MarketSource]:
    query = (
        select(MarketSource)
        .join(CanonicalKnowledgeAsset, CanonicalKnowledgeAsset.id == MarketSource.asset_id)
        .where(CanonicalKnowledgeAsset.canonical_product_id == product_id)
        .options(
            selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.locations),
            selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.labels),
            selectinload(MarketSource.asset).selectinload(CanonicalKnowledgeAsset.capabilities),
        )
        .order_by(MarketSource.id)
    )
    return list((await db.execute(query)).unique().scalars())


async def discover_candidates_for_item(
    db: AsyncSession,
    *,
    item: MarketUpdateItem,
    product: CanonicalProduct,
    force_rediscovery: bool,
    competitor_limit: int,
    discover: Callable[..., Awaitable[dict[str, Any]]],
) -> DiscoveryOutcome:
    """Completa la cobertura de un item y persiste candidatas en cuarentena."""
    sources = await _product_market_sources(db, product.id)
    confirmed_urls = [
        source.url
        for source in sources
        if source.url
        and source.asset.status == "confirmed"
        and source.is_active
        and source.validation_status == "verified"
        and source.source_type != "manual"
    ]
    existing_keys = {competitor_key(url) for url in confirmed_urls if competitor_key(url)}
    item.competitors_existing = len(existing_keys)
    if len(existing_keys) >= competitor_limit and not force_rediscovery:
        await db.commit()
        return DiscoveryOutcome([])

    item.stage = "discovering"
    await db.commit()
    result = await discover(
        product_name=product.name or "",
        category="",
        sku=product.ng_sku or "",
        existing_urls=[],
        max_results=30,
        user_role="admin",
    )
    if not result.get("success"):
        raw_error = result.get("error")
        code = (
            str(raw_error.get("code") or "market_discovery_failed")
            if isinstance(raw_error, dict)
            else str(raw_error or "market_discovery_failed")
        )[:64]
        item.error_code = code
        item.error_message = (
            str(raw_error.get("message") or "No se pudieron descubrir competidores")
            if isinstance(raw_error, dict)
            else "No se pudieron descubrir competidores"
        )[:1000]
        await db.commit()
        return DiscoveryOutcome([], code, item.error_message)

    blocked_urls = [
        source.url
        for source in sources
        if source.url and (source.asset.status == "archived" or source.url not in confirmed_urls)
    ]
    selected = select_missing_competitors(
        result.get("sources", []),
        existing_urls=confirmed_urls,
        archived_urls=blocked_urls,
        limit=competitor_limit,
    )
    candidates: list[MarketSource] = []
    item.stage = "validating"
    for candidate in selected:
        url = str(candidate.get("url") or "")
        try:
            validate_public_url(url)
            asset = await create_asset(
                db,
                canonical_product_id=product.id,
                title=(str(candidate.get("title") or competitor_key(url))[:200]),
                asset_type="web",
                labels={"market"},
                capabilities={"price", "availability", "offers"},
                url=url,
                exclude_from_enrichment=False,
                status="pending",
                origin="market_discovery",
                user_id=None,
            )
        except (ValueError, HTTPException):
            continue
        source = asset.market_profile
        if source is None:
            continue
        source.is_active = False
        source.validation_status = "warning"
        source.ars_confirmed = None
        source.argentina_delivery_confirmed = has_argentina_delivery_evidence(
            url, str(candidate.get("snippet") or "")
        )
        source.validation_detail = {
            "origin": "market_discovery",
            "competitor_key": competitor_key(url),
            "snippet_delivery_evidence": source.argentina_delivery_confirmed,
        }
        source.last_error_code = "pending_initial_validation"
        source.last_error_message = "Pendiente de confirmar precio ARS y entrega en Argentina"
        await db.commit()
        candidates.append(source)
    item.sources_discovered = len(candidates)
    await db.commit()
    return DiscoveryOutcome(candidates)
