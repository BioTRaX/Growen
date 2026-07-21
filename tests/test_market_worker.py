#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_worker.py
# NG-HEADER: Ubicación: tests/test_market_worker.py
# NG-HEADER: Descripción: Regresiones del worker Mercado y detección de variaciones.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from decimal import Decimal

import pytest
from sqlalchemy import select

from db.models import CanonicalProduct, MarketAlert, MarketSource
from services.market.alerts import detect_price_alerts
from workers import market_scraping


@pytest.mark.asyncio
async def test_all_sources_failed_returns_failed_status(db_session, monkeypatch):
    product = CanonicalProduct(name="Producto sin precio actualizado")
    db_session.add(product)
    await db_session.flush()
    source = MarketSource(
        product_id=product.id,
        source_name="Fuente caída",
        url="https://example.com/failing-product",
        currency="ARS",
        source_type="static",
    )
    db_session.add(source)
    await db_session.commit()

    async def fail_scrape(*_args, **_kwargs):
        return None, None, "timeout", False

    monkeypatch.setattr(market_scraping, "scrape_market_source", fail_scrape)

    result = await market_scraping.update_market_prices_for_product(product.id, db_session)

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["sources_failed"] == 1
    await db_session.refresh(source)
    assert source.last_checked_at is not None


@pytest.mark.asyncio
async def test_foreign_currency_is_not_averaged_as_ars(db_session, monkeypatch):
    product = CanonicalProduct(
        name="Producto importado",
        market_price_reference=Decimal("1000.00"),
    )
    db_session.add(product)
    await db_session.flush()
    source = MarketSource(
        product_id=product.id,
        source_name="Fuente USD",
        url="https://example.com/usd-product",
        currency="USD",
        source_type="static",
    )
    db_session.add(source)
    await db_session.commit()

    async def usd_scrape(*_args, **_kwargs):
        return Decimal("50.00"), "USD", None, False

    monkeypatch.setattr(market_scraping, "scrape_market_source", usd_scrape)

    result = await market_scraping.update_market_prices_for_product(product.id, db_session)

    assert result["success"] is True
    assert result["market_price_reference"] is None
    await db_session.refresh(product)
    await db_session.refresh(source)
    assert product.market_price_reference == Decimal("1000.00")
    assert source.last_price == Decimal("50.00")
    assert source.currency == "USD"


@pytest.mark.asyncio
async def test_alert_uses_previous_market_price_explicitly(db_session):
    product = CanonicalProduct(
        name="Producto con variación",
        market_price_reference=Decimal("150.00"),
    )
    db_session.add(product)
    await db_session.commit()

    alerts = await detect_price_alerts(
        db=db_session,
        product_id=product.id,
        new_market_price=Decimal("150.00"),
        previous_market_price=Decimal("100.00"),
    )

    assert len(alerts) == 1
    stored = await db_session.scalar(select(MarketAlert).where(MarketAlert.product_id == product.id))
    assert stored is not None
    assert stored.alert_type == "market_spike"
    assert stored.old_value == Decimal("100.00")
    assert stored.new_value == Decimal("150.00")
