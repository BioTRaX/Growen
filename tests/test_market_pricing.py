#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_pricing.py
# NG-HEADER: Ubicación: tests/test_market_pricing.py
# NG-HEADER: Descripción: Pruebas de promedio ARS y bandas de comparación de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from db.models import CanonicalProduct, MarketPriceHistory, MarketSource
from services.market.jobs import create_update_job
from services.market.pricing import compare_sale_to_market, recompute_market_reference


@pytest.mark.parametrize(
    ("sale", "expected"),
    [
        ("80", "much_cheaper"),
        ("80.01", "very_cheaper"),
        ("85", "very_cheaper"),
        ("85.01", "moderately_cheaper"),
        ("90", "moderately_cheaper"),
        ("90.01", "slightly_cheaper"),
        ("94.99", "slightly_cheaper"),
        ("95", "aligned"),
        ("105", "aligned"),
        ("105.01", "slightly_expensive"),
        ("109.99", "slightly_expensive"),
        ("110", "moderately_expensive"),
        ("114.99", "moderately_expensive"),
        ("115", "very_expensive"),
    ],
)
def test_price_comparison_exact_boundaries(sale: str, expected: str):
    comparison = compare_sale_to_market(Decimal(sale), Decimal("100"))
    assert comparison.position == expected


@pytest.mark.parametrize("sale,market", [(None, "100"), ("100", None), ("0", "100"), ("100", "0")])
def test_price_comparison_unavailable_without_positive_values(sale, market):
    assert compare_sale_to_market(sale, market).position == "unavailable"


@pytest.mark.asyncio
async def test_reference_averages_one_effective_ars_observation_per_source(db_session):
    product = CanonicalProduct(name="Promedio ARS")
    db_session.add(product)
    await db_session.flush()
    sources = [
        MarketSource(product_id=product.id, source_name="Obligatoria", url="https://a.example/item", currency="ARS", source_type="static", is_mandatory=True, validation_status="verified"),
        MarketSource(product_id=product.id, source_name="Adicional", url="https://b.example/item", currency="ARS", source_type="static", is_mandatory=False, validation_status="warning"),
        MarketSource(product_id=product.id, source_name="Rechazada", url="https://c.example/item", currency="ARS", source_type="static", validation_status="rejected"),
    ]
    db_session.add_all(sources)
    await db_session.flush()
    db_session.add_all([
        MarketPriceHistory(product_id=product.id, source_id=sources[0].id, price=Decimal("100"), currency="ARS", observation_type="source", capture_method="static"),
        MarketPriceHistory(product_id=product.id, source_id=sources[1].id, price=Decimal("200"), currency="ARS", observation_type="source", capture_method="static"),
        MarketPriceHistory(product_id=product.id, source_id=sources[2].id, price=Decimal("900"), currency="ARS", observation_type="source", capture_method="static"),
    ])
    await db_session.flush()

    reference, coverage, snapshot = await recompute_market_reference(db_session, product_id=product.id)

    assert reference == Decimal("150.00")
    assert coverage.effective == 2
    assert coverage.warning == 1
    assert snapshot is not None and snapshot.observation_type == "reference"


@pytest.mark.asyncio
async def test_stale_automatic_expires_but_manual_remains_effective(db_session):
    product = CanonicalProduct(name="Vigencias")
    db_session.add(product)
    await db_session.flush()
    automatic = MarketSource(product_id=product.id, source_name="Automática", url="https://a.example/stale", currency="ARS", source_type="static")
    manual = MarketSource(product_id=product.id, source_name="Manual", url=None, currency="ARS", source_type="manual")
    db_session.add_all([automatic, manual])
    await db_session.flush()
    old = datetime.utcnow() - timedelta(days=30)
    db_session.add_all([
        MarketPriceHistory(product_id=product.id, source_id=automatic.id, price=Decimal("100"), currency="ARS", observation_type="source", capture_method="static", created_at=old),
        MarketPriceHistory(product_id=product.id, source_id=manual.id, price=Decimal("250"), currency="ARS", observation_type="source", capture_method="manual", created_at=old),
    ])
    await db_session.flush()

    reference, coverage, _ = await recompute_market_reference(db_session, product_id=product.id)

    assert reference == Decimal("250.00")
    assert coverage.effective == 1
    assert coverage.stale == 1


@pytest.mark.asyncio
async def test_duplicate_request_reuses_active_item(db_session):
    product = CanonicalProduct(name="Idempotente")
    db_session.add(product)
    await db_session.commit()
    first = await create_update_job(db_session, [product.id], trigger="test")
    second = await create_update_job(db_session, [product.id], trigger="test")

    assert first.items[0].deduplicated is False
    assert second.items[0].deduplicated is True
    assert second.items[0].item_id == first.items[0].item_id
