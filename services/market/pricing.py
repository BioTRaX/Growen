#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: pricing.py
# NG-HEADER: Ubicación: services/market/pricing.py
# NG-HEADER: Descripción: Reglas ARS, vigencia, promedio y posición de precios de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Reglas de negocio autoritativas para precios de Mercado."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CanonicalKnowledgeAsset,
    CanonicalKnowledgeAssetCapability,
    CanonicalKnowledgeLabel,
    CanonicalProduct,
    MarketPriceHistory,
    MarketSource,
    MarketUpdateJob,
)


AUTOMATIC_FRESHNESS_DAYS = int(os.getenv("MARKET_PRICE_FRESHNESS_DAYS", "7"))
ARS = "ARS"
HISTORY_RETENTION_DAYS = int(os.getenv("MARKET_HISTORY_RETENTION_DAYS", str(365 * 3)))


@dataclass(frozen=True)
class PriceComparison:
    delta_pct: Decimal | None
    position: str
    label: str


@dataclass(frozen=True)
class MarketCoverage:
    effective: int
    stale: int
    warning: int


def eligible_market_profile_conditions(*, allow_manual: bool = True):
    """Condiciones compartidas para que un perfil pueda aportar a Mercado."""
    attestation = and_(
        MarketSource.ars_confirmed.is_(True),
        MarketSource.argentina_delivery_confirmed.is_(True),
    )
    if allow_manual:
        attestation = or_(MarketSource.source_type == "manual", attestation)
    return (
        CanonicalKnowledgeAsset.status == "confirmed",
        CanonicalKnowledgeLabel.label == "market",
        CanonicalKnowledgeAssetCapability.capability_code == "price",
        CanonicalKnowledgeAssetCapability.enabled.is_(True),
        MarketSource.is_active.is_(True),
        MarketSource.validation_status != "rejected",
        MarketSource.currency == ARS,
        attestation,
    )


def compare_sale_to_market(
    sale_price: Decimal | int | float | None,
    market_price: Decimal | int | float | None,
) -> PriceComparison:
    """Clasifica con Decimal sin redondear; el porcentaje expuesto usa dos decimales."""
    if sale_price is None or market_price is None:
        return PriceComparison(None, "unavailable", "Sin comparación")
    sale = Decimal(str(sale_price))
    market = Decimal(str(market_price))
    if sale <= 0 or market <= 0:
        return PriceComparison(None, "unavailable", "Sin comparación")

    raw = ((sale - market) / market) * Decimal("100")
    shown = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if raw <= Decimal("-20"):
        position, text = "much_cheaper", "Mucho más barato"
    elif raw <= Decimal("-15"):
        position, text = "very_cheaper", "Muy barato"
    elif raw <= Decimal("-10"):
        position, text = "moderately_cheaper", "Moderadamente barato"
    elif raw < Decimal("-5"):
        position, text = "slightly_cheaper", "Algo más barato"
    elif raw <= Decimal("5"):
        position, text = "aligned", "Alineado al mercado"
    elif raw < Decimal("10"):
        position, text = "slightly_expensive", "Algo más caro"
    elif raw < Decimal("15"):
        position, text = "moderately_expensive", "Moderadamente caro"
    else:
        position, text = "very_expensive", "Mucho más caro"
    return PriceComparison(shown, position, text)


async def effective_source_prices(
    db: AsyncSession,
    product_id: int,
    *,
    now: datetime | None = None,
    freshness_days: int = AUTOMATIC_FRESHNESS_DAYS,
) -> tuple[list[tuple[MarketSource, MarketPriceHistory]], MarketCoverage]:
    """Obtiene la última observación ARS efectiva de cada fuente activa."""
    current = now or datetime.utcnow()
    sources = list((await db.execute(
        select(MarketSource)
        .join(CanonicalKnowledgeAsset, CanonicalKnowledgeAsset.id == MarketSource.asset_id)
        .join(CanonicalKnowledgeLabel, CanonicalKnowledgeLabel.asset_id == CanonicalKnowledgeAsset.id)
        .join(
            CanonicalKnowledgeAssetCapability,
            CanonicalKnowledgeAssetCapability.asset_id == CanonicalKnowledgeAsset.id,
        )
        .where(
            CanonicalKnowledgeAsset.canonical_product_id == product_id,
            *eligible_market_profile_conditions(),
        )
        .order_by(MarketSource.id)
    )).scalars())
    effective: list[tuple[MarketSource, MarketPriceHistory]] = []
    stale = 0
    warnings = 0
    for source in sources:
        if source.validation_status == "rejected" or (source.currency or ARS).upper() != ARS:
            continue
        observation = await db.scalar(
            select(MarketPriceHistory)
            .where(
                MarketPriceHistory.product_id == product_id,
                MarketPriceHistory.source_id == source.id,
                MarketPriceHistory.observation_type == "source",
                MarketPriceHistory.currency == ARS,
            )
            .order_by(MarketPriceHistory.created_at.desc(), MarketPriceHistory.id.desc())
            .limit(1)
        )
        if not observation:
            continue
        if source.validation_status == "warning":
            warnings += 1
        if observation.capture_method != "manual" and observation.created_at < current - timedelta(days=freshness_days):
            stale += 1
            continue
        effective.append((source, observation))
    return effective, MarketCoverage(len(effective), stale, warnings)


async def persist_source_observation(
    db: AsyncSession,
    *,
    product_id: int,
    source: MarketSource,
    price: Decimal,
    capture_method: str,
    job_id: str | None = None,
    job_item_id: int | None = None,
    created_by_user_id: int | None = None,
) -> MarketPriceHistory:
    """Registra una observación ARS inmutable y actualiza el cache de la fuente."""
    if price <= 0:
        raise ValueError("El precio debe ser mayor a cero")
    if (source.currency or ARS).upper() != ARS:
        raise ValueError("Mercado sólo admite observaciones en ARS")
    previous = await db.scalar(
        select(MarketPriceHistory)
        .where(MarketPriceHistory.source_id == source.id, MarketPriceHistory.observation_type == "source")
        .order_by(MarketPriceHistory.created_at.desc(), MarketPriceHistory.id.desc())
        .limit(1)
    )
    change = None
    if previous and previous.price:
        change = ((price - Decimal(previous.price)) / Decimal(previous.price) * Decimal("100")).quantize(Decimal("0.01"))
    observed = MarketPriceHistory(
        product_id=product_id,
        source_id=source.id,
        price=price.quantize(Decimal("0.01")),
        currency=ARS,
        source_url=source.url,
        source_name=source.source_name,
        price_change_pct=change,
        observation_type="source",
        capture_method=capture_method,
        job_id=job_id,
        job_item_id=job_item_id,
        created_by_user_id=created_by_user_id,
    )
    db.add(observed)
    source.last_price = observed.price
    source.last_checked_at = datetime.utcnow()
    source.last_success_at = source.last_checked_at
    source.last_error_at = None
    source.last_error_code = None
    source.last_error_message = None
    await db.flush()
    return observed


async def recompute_market_reference(
    db: AsyncSession,
    *,
    product_id: int,
    job_id: str | None = None,
    job_item_id: int | None = None,
    created_by_user_id: int | None = None,
) -> tuple[Decimal | None, MarketCoverage, MarketPriceHistory | None]:
    """Recalcula el promedio efectivo y persiste un snapshot de referencia."""
    product = await db.get(CanonicalProduct, product_id)
    if not product:
        raise LookupError(f"Producto {product_id} no encontrado")
    effective, coverage = await effective_source_prices(db, product_id)
    product.market_price_updated_at = datetime.utcnow()
    if not effective:
        product.market_price_reference = None
        return None, coverage, None
    prices = [Decimal(observation.price) for _, observation in effective]
    reference = (sum(prices, Decimal("0")) / Decimal(len(prices))).quantize(Decimal("0.01"))
    product.market_price_reference = reference
    snapshot = MarketPriceHistory(
        product_id=product_id,
        source_id=None,
        price=reference,
        currency=ARS,
        source_name="Promedio de mercado",
        observation_type="reference",
        capture_method="manual" if all(obs.capture_method == "manual" for _, obs in effective) else "static",
        job_id=job_id,
        job_item_id=job_item_id,
        created_by_user_id=created_by_user_id,
    )
    db.add(snapshot)
    await db.flush()
    return reference, coverage, snapshot


async def cleanup_market_history(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    retention_days: int = HISTORY_RETENTION_DAYS,
) -> dict[str, int]:
    """Elimina únicamente trazabilidad Mercado vencida según la retención configurada."""
    cutoff = (now or datetime.utcnow()) - timedelta(days=retention_days)
    observations = await db.execute(
        delete(MarketPriceHistory).where(MarketPriceHistory.created_at < cutoff)
    )
    jobs = await db.execute(
        delete(MarketUpdateJob).where(
            MarketUpdateJob.created_at < cutoff,
            MarketUpdateJob.status.in_(("partial", "succeeded", "failed", "cancelled")),
        )
    )
    await db.commit()
    return {"observations": observations.rowcount or 0, "jobs": jobs.rowcount or 0}
