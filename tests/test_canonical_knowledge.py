#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_knowledge.py
# NG-HEADER: Ubicación: tests/test_canonical_knowledge.py
# NG-HEADER: Descripción: Contratos, confianza, deduplicación y revisión del conocimiento canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest

from db.models import CanonicalProduct
from db.models import CanonicalKnowledgeAsset
from services.jobs.knowledge_jobs import _ai_extract
from services.knowledge.service import deterministic_trust


@pytest.mark.asyncio
async def test_knowledge_crud_uses_separate_labels_and_optimistic_revision(client_collab, db_session):
    canonical = CanonicalProduct(name="Root Complex", ng_sku="NG-990001", brand="Hesi")
    db_session.add(canonical)
    await db_session.commit()

    created = await client_collab.post(
        f"/canonical-products/{canonical.id}/knowledge",
        json={
            "title": "Fabricante Hesi",
            "asset_type": "web",
            "url": "https://hesi.nl/en/products/root-complex",
            "labels": ["manufacturer", "official"],
            "capabilities": ["description", "technical_specs"],
        },
    )
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["labels"] == ["manufacturer", "official"]
    assert asset["trust_score"] > 0

    duplicate = await client_collab.post(
        f"/canonical-products/{canonical.id}/knowledge",
        json={
            "title": "Duplicada",
            "asset_type": "web",
            "url": "https://HESI.nl/en/products/root-complex#details",
            "labels": ["manufacturer"],
        },
    )
    assert duplicate.status_code == 409

    stale = await client_collab.patch(
        f"/canonical-products/{canonical.id}/knowledge/{asset['id']}",
        json={
            "expected_revision": asset["revision"] + 1,
            "title": "No debe guardarse",
        },
    )
    assert stale.status_code == 409

    listed = await client_collab.get(f"/canonical-products/{canonical.id}/knowledge")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["labels"] == ["manufacturer", "official"]
    jobs = await client_collab.get(f"/canonical-products/{canonical.id}/knowledge/jobs")
    assert jobs.status_code == 200


@pytest.mark.asyncio
async def test_market_asset_requires_and_persists_argentina_attestation(client_collab, db_session):
    canonical = CanonicalProduct(name="Fuente Mercado", ng_sku="NG-990002")
    db_session.add(canonical)
    await db_session.commit()

    created = await client_collab.post(
        f"/canonical-products/{canonical.id}/knowledge",
        json={
            "title": "Comercio argentino",
            "asset_type": "web",
            "url": "https://example.com/producto",
            "labels": ["market"],
            "capabilities": ["price", "availability", "offers"],
        },
    )
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["market"]["validation_status"] == "warning"
    assert asset["market"]["argentina_delivery_confirmed"] is False

    verified = await client_collab.patch(
        f"/canonical-products/{canonical.id}/knowledge/{asset['id']}",
        json={
            "expected_revision": asset["revision"],
            "market_is_active": True,
            "market_is_mandatory": True,
            "market_source_type": "static",
            "market_argentina_delivery_confirmed": True,
        },
    )
    assert verified.status_code == 200, verified.text
    market = verified.json()["market"]
    assert market["validation_status"] == "verified"
    assert market["ars_confirmed"] is True
    assert market["argentina_delivery_confirmed"] is True
    assert market["is_mandatory"] is True


def test_hybrid_trust_weights_and_ai_bounds_are_auditable():
    score, breakdown = deterministic_trust(
        {"manufacturer", "official"},
        validated=True,
        fresh=True,
        agreement=1,
        extraction_success=1,
    )
    assert score == 100
    assert breakdown["weights"] == {
        "authority": 0.40,
        "validation": 0.20,
        "freshness": 0.15,
        "agreement": 0.15,
        "extraction_success": 0.10,
    }


@pytest.mark.asyncio
async def test_invalid_ai_schema_does_not_fail_knowledge_ingestion(monkeypatch):
    async def invalid_json(*_args, **_kwargs):
        return "respuesta sin estructura"

    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setattr(
        "services.jobs.knowledge_jobs.OpenAIProvider.generate_async",
        invalid_json,
    )
    asset = CanonicalKnowledgeAsset(
        canonical_product_id=1,
        title="Activo",
        asset_type="web",
    )
    claims, adjustment, reason = await _ai_extract(asset, "Contenido con datos")
    assert claims == []
    assert adjustment is None
    assert reason is None
