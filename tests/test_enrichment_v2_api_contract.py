#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_enrichment_v2_api_contract.py
# NG-HEADER: Ubicación: tests/test_enrichment_v2_api_contract.py
# NG-HEADER: Descripción: Idempotencia, job activo y revisión optimista de Enrich v2.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from fastapi import HTTPException

from db.models import CanonicalEnrichmentJob, CanonicalProduct
from services.auth import SessionData
from services.routers.enrichment import (
    EnrichmentApplyRequest,
    apply_enrichment_job,
    create_enrichment_job,
    get_catalog_audit_report,
    get_enrichment_summary,
    serialize_job,
)


@pytest.mark.asyncio
async def test_job_creation_is_idempotent_and_rejects_second_active_job(db_session):
    canonical = CanonicalProduct(name="Canónico", ng_sku="NG-800001")
    db_session.add(canonical)
    await db_session.commit()
    first, created = await create_enrichment_job(
        db_session,
        canonical_id=canonical.id,
        requested_product_id=None,
        client_request_id="same-request",
        scope="full",
        requested_by_user_id=None,
    )
    duplicate, duplicate_created = await create_enrichment_job(
        db_session,
        canonical_id=canonical.id,
        requested_product_id=None,
        client_request_id="same-request",
        scope="full",
        requested_by_user_id=None,
    )
    assert created is True
    assert duplicate_created is False
    assert duplicate.id == first.id
    with pytest.raises(HTTPException) as conflict:
        await create_enrichment_job(
            db_session,
            canonical_id=canonical.id,
            requested_product_id=None,
            client_request_id="second-request",
            scope="description",
            requested_by_user_id=None,
        )
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_uses_optimistic_content_revision(db_session):
    canonical = CanonicalProduct(name="Canónico", ng_sku="NG-800002", content_revision=3)
    db_session.add(canonical)
    await db_session.commit()
    job, _ = await create_enrichment_job(
        db_session,
        canonical_id=canonical.id,
        requested_product_id=None,
        client_request_id="apply-request",
        scope="description",
        requested_by_user_id=None,
    )
    job.status = "review_required"
    job.result_json = {
        "proposal": {"description_html": "<p>Descripción segura.</p>"},
        "confidence": {"description_html": 0.91},
    }
    await db_session.commit()
    result = await apply_enrichment_job(
        canonical.id,
        job.id,
        EnrichmentApplyRequest(fields=["description_html"], expected_content_revision=3),
        db_session,
        SessionData(None, None, "admin"),
    )
    assert result["content_revision"] == 4
    with pytest.raises(HTTPException) as conflict:
        await apply_enrichment_job(
            canonical.id,
            job.id,
            EnrichmentApplyRequest(fields=["description_html"], expected_content_revision=3),
            db_session,
            SessionData(None, None, "admin"),
        )
    assert conflict.value.status_code == 409


def test_job_contract_exposes_persisted_provider_diagnostics():
    job = CanonicalEnrichmentJob(
        id="diagnostic-job",
        canonical_product_id=1,
        client_request_id="diagnostic-request",
        scope="full",
        result_json={
            "provider_diagnostics": [
                {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "status": "failed",
                    "code": "insufficient_quota",
                    "http_status": 429,
                }
            ]
        },
    )
    job.sources = []

    payload = serialize_job(job)

    assert payload["provider_diagnostics"][0]["code"] == "insufficient_quota"
    assert payload["provider_diagnostics"][0]["http_status"] == 429


@pytest.mark.asyncio
async def test_get_enrichment_summary_contract(db_session):
    canonical = CanonicalProduct(name="Producto Resumen", ng_sku="NG-900001", content_revision=1)
    db_session.add(canonical)
    await db_session.commit()

    job, _ = await create_enrichment_job(
        db_session,
        canonical_id=canonical.id,
        requested_product_id=None,
        client_request_id="summary-request-1",
        scope="full",
        requested_by_user_id=None,
    )
    job.status = "review_required"
    job.result_json = {
        "quality_audit": {
            "score": 95,
            "passed": True,
            "warnings": [],
        }
    }
    await db_session.commit()

    summary = await get_enrichment_summary(
        session=db_session,
        _user=SessionData(None, None, "admin"),
    )
    assert "worker" in summary
    assert summary["worker"]["name"] == "enrichment_worker"
    assert "jobs" in summary
    assert summary["jobs"]["total"] >= 1
    assert summary["jobs"]["by_status"].get("review_required", 0) >= 1
    assert len(summary["jobs"]["recent"]) >= 1
    assert summary["jobs"]["recent"][0]["quality_score"] == 95
    assert "catalog_coverage" in summary
    assert summary["catalog_coverage"]["total_canonical"] >= 1


@pytest.mark.asyncio
async def test_get_catalog_audit_report_contract(db_session):
    clean_p = CanonicalProduct(
        name="Top Crop Deeper Underground 250ml",
        brand="Top Crop",
        ng_sku="NG-900002",
        weight_kg=0.28,
        height_cm=14.0,
        width_cm=6.0,
        depth_cm=6.0,
        description_html="<p>Estimulador de raíces orgánico.</p>",
    )
    bad_p = CanonicalProduct(
        name="Sustrato Top Crop Heavy Mix 50L",
        brand="Top Crop",
        ng_sku="NG-900003",
        weight_kg=80.0,
        height_cm=80.0,
        width_cm=40.0,
        depth_cm=20.0,
        description_html="<p>Sustrato completo.</p>",
    )
    db_session.add_all([clean_p, bad_p])
    await db_session.commit()

    report = await get_catalog_audit_report(
        limit=50,
        session=db_session,
        _user=SessionData(None, None, "admin"),
    )
    assert report["total_audited"] >= 2
    assert report["issues_count"] >= 1
    issue_ids = [issue["canonical_product_id"] for issue in report["issues"]]
    assert bad_p.id in issue_ids
