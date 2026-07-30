#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_enrichment_v2_api_contract.py
# NG-HEADER: Ubicación: tests/test_enrichment_v2_api_contract.py
# NG-HEADER: Descripción: Idempotencia, job activo y revisión optimista de Enrich v2.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from fastapi import HTTPException

from db.models import CanonicalProduct
from services.auth import SessionData
from services.routers.enrichment import (
    EnrichmentApplyRequest,
    apply_enrichment_job,
    create_enrichment_job,
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
