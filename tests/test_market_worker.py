#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_worker.py
# NG-HEADER: Ubicación: tests/test_market_worker.py
# NG-HEADER: Descripción: Regresiones del worker Mercado y detección de variaciones.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from db.models import CanonicalProduct, MarketAlert, MarketPriceHistory, MarketSource
from services.market.alerts import detect_price_alerts
from services.market.jobs import create_update_job
from workers import market_scraping


def test_market_worker_pool_is_safe_across_dramatiq_thread_event_loops() -> None:
    assert isinstance(market_scraping.engine.pool, NullPool)


def test_source_failure_prioritizes_http_over_incomplete_delivery() -> None:
    code, message, retryable, http_status = market_scraping._source_failure(
        price=None,
        currency_is_ars=False,
        is_candidate=True,
        delivery_confirmed=False,
        error="Error de red: Error HTTP 404: Not Found",
    )

    assert code == "http_404"
    assert "404" in message
    assert retryable is False
    assert http_status == 404


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
        ars_confirmed=True,
        argentina_delivery_confirmed=True,
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
async def test_foreign_currency_is_not_processed_as_ars(db_session, monkeypatch):
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
    assert result["sources_total"] == 0
    await db_session.refresh(product)
    await db_session.refresh(source)
    assert product.market_price_reference == Decimal("1000.00")
    assert source.last_price is None
    assert source.currency == "USD"


@pytest.mark.asyncio
async def test_targeted_detection_persists_price_but_keeps_unvalidated_source_quarantined(
    db_session, monkeypatch
):
    product = CanonicalProduct(name="Producto con fuente pendiente")
    db_session.add(product)
    await db_session.flush()
    source = MarketSource(
        product_id=product.id,
        source_name="Competidor pendiente",
        url="https://example.com/producto",
        currency="ARS",
        is_active=False,
        validation_status="warning",
        argentina_delivery_confirmed=False,
    )
    source.asset.origin = "market_discovery"
    source.asset.status = "pending"
    db_session.add(source)
    await db_session.commit()
    queued = await create_update_job(
        db_session,
        [product.id],
        trigger="source_price_detection",
        target_source_id=source.id,
    )

    class SessionContext:
        async def __aenter__(self): return db_session
        async def __aexit__(self, *_args): return False

    class Lock:
        def acquire(self): return True
        def release(self): return None

    async def captured_price(*_args, **_kwargs):
        return Decimal("3700.00"), "ARS", None, False

    monkeypatch.setattr(market_scraping, "SessionLocal", SessionContext)
    monkeypatch.setattr(market_scraping, "_domain_lock", lambda _url: Lock())
    monkeypatch.setattr(market_scraping, "scrape_market_source", captured_price)

    result = await market_scraping.process_market_item(queued.items[0].item_id)

    await db_session.refresh(source)
    await db_session.refresh(product)
    observation = await db_session.scalar(
        select(MarketPriceHistory).where(MarketPriceHistory.source_id == source.id)
    )
    assert result["status"] == "succeeded"
    assert observation.price == Decimal("3700.00")
    assert source.last_price == Decimal("3700.00")
    assert source.is_active is False
    assert source.validation_status == "warning"
    assert source.last_error_code == "argentina_delivery_unconfirmed"
    assert product.market_price_reference is None


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
