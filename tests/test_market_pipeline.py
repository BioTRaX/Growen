#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_pipeline.py
# NG-HEADER: Ubicación: tests/test_market_pipeline.py
# NG-HEADER: Descripción: Regresiones del pipeline automático de descubrimiento y extracción de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from db.models import CanonicalProduct, MarketUpdateItem, MarketUpdateJob, MarketUpdateSourceResult
from services.market.jobs import create_update_job, expire_stale_items, job_payload
from services.market.pipeline import competitor_key, has_argentina_delivery_evidence, select_missing_competitors


@pytest.mark.no_db
def test_competitor_key_groups_marketplace_aliases_and_www() -> None:
    assert competitor_key("https://www.mercadolibre.com.ar/item/1") == "mercadolibre.com.ar"
    assert competitor_key("https://articulo.mercadolibre.com.ar/MLA-1") == "mercadolibre.com.ar"
    assert competitor_key("https://www.santaplanta.com/producto") == "santaplanta.com"


@pytest.mark.no_db
def test_select_missing_competitors_limits_distinct_domains_to_three() -> None:
    candidates = [
        {"url": "https://www.mercadolibre.com.ar/a", "title": "ML A", "snippet": "$ 1"},
        {"url": "https://articulo.mercadolibre.com.ar/b", "title": "ML B", "snippet": "$ 2"},
        {"url": "https://santaplanta.com/a", "title": "Santa", "snippet": "$ 3"},
        {"url": "https://tricomas.com.ar/a", "title": "Tricomas", "snippet": "$ 4"},
        {"url": "https://easy.com.ar/a", "title": "Easy", "snippet": "$ 5"},
    ]

    selected = select_missing_competitors(
        candidates,
        existing_urls=["https://santaplanta.com/existente"],
        archived_urls=["https://tricomas.com.ar/archivada"],
        limit=3,
    )

    assert [competitor_key(item["url"]) for item in selected] == [
        "mercadolibre.com.ar",
        "easy.com.ar",
    ]


@pytest.mark.no_db
def test_select_missing_competitors_does_not_exceed_complete_coverage() -> None:
    assert select_missing_competitors(
        [{"url": "https://nuevo.example/producto"}],
        existing_urls=[
            "https://uno.example/a",
            "https://dos.example/b",
            "https://tres.example/c",
        ],
        archived_urls=[],
        limit=3,
    ) == []


@pytest.mark.no_db
def test_delivery_evidence_requires_argentina_or_domestic_ar_context() -> None:
    assert has_argentina_delivery_evidence("https://tienda.example", "Entregas en Argentina")
    assert has_argentina_delivery_evidence("https://tienda.com.ar/p", "Envíos a todo el país")
    assert not has_argentina_delivery_evidence("https://tienda.cl/p", "Envíos a todo Chile")


@pytest.mark.asyncio
async def test_refresh_rejects_unavailable_worker_without_orphan_job(
    client_collab, db, monkeypatch
) -> None:
    product = CanonicalProduct(name="Producto sin worker")
    db.add(product)
    await db.commit()

    async def unavailable():
        return {"ok": False, "broker_ok": False}

    monkeypatch.setenv("RUN_INLINE_JOBS", "0")
    monkeypatch.setattr("services.routers.health.health_market_worker", unavailable)
    response = await client_collab.post(
        f"/market/products/{product.id}/refresh-market",
        json={"force_rediscovery": False},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "market_worker_unavailable"
    assert await db.scalar(select(func.count()).select_from(MarketUpdateJob)) == 0


@pytest.mark.asyncio
async def test_job_payload_exposes_pipeline_stage_and_discovery_counters(db_session) -> None:
    product = CanonicalProduct(name="Producto pipeline")
    db_session.add(product)
    await db_session.commit()

    result = await create_update_job(
        db_session,
        [product.id],
        trigger="batch",
        force_rediscovery=True,
    )
    item = await db_session.get(MarketUpdateItem, result.items[0].item_id)
    item.stage = "discovering"
    item.competitors_existing = 1
    item.sources_discovered = 2
    item.sources_confirmed = 1
    item.sources_quarantined = 1
    db_session.add(MarketUpdateSourceResult(
        item_id=item.id,
        operation="validation",
        status="failed",
        error_code="argentina_delivery_unconfirmed",
        retryable=False,
    ))
    await db_session.commit()

    payload = await job_payload(db_session, result.job.id)

    assert payload["config_snapshot"]["competitor_limit"] == 3
    assert payload["config_snapshot"]["force_rediscovery"] is True
    assert payload["items"][0]["stage"] == "discovering"
    assert payload["items"][0]["competitors_existing"] == 1
    assert payload["items"][0]["sources_discovered"] == 2
    assert payload["items"][0]["sources_confirmed"] == 1
    assert payload["items"][0]["sources_quarantined"] == 1
    assert payload["items"][0]["source_results"][0]["operation"] == "validation"


@pytest.mark.asyncio
async def test_targeted_price_job_records_source_and_disables_discovery(db_session) -> None:
    product = CanonicalProduct(name="Producto con detección focal")
    db_session.add(product)
    await db_session.commit()

    result = await create_update_job(
        db_session,
        [product.id],
        trigger="source_price_detection",
        target_source_id=77,
    )

    payload = await job_payload(db_session, result.job.id)
    assert payload["config_snapshot"]["target_source_id"] == 77
    assert payload["config_snapshot"]["force_price_detection"] is True
    assert payload["config_snapshot"]["force_rediscovery"] is False


@pytest.mark.asyncio
async def test_expire_stale_item_finishes_job_and_releases_product(db_session) -> None:
    product = CanonicalProduct(name="Producto con lease vencido")
    db_session.add(product)
    await db_session.commit()
    first = await create_update_job(db_session, [product.id], trigger="batch")
    item = await db_session.get(MarketUpdateItem, first.items[0].item_id)
    item.created_at = datetime.utcnow() - timedelta(minutes=10)
    await db_session.commit()

    expired = await expire_stale_items(db_session, now=datetime.utcnow())
    second = await create_update_job(db_session, [product.id], trigger="batch")

    assert expired == 1
    assert (await job_payload(db_session, first.job.id))["status"] == "failed"
    assert second.items[0].deduplicated is False
