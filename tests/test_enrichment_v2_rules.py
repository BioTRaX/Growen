#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_enrichment_v2_rules.py
# NG-HEADER: Ubicación: tests/test_enrichment_v2_rules.py
# NG-HEADER: Descripción: Reglas de validación y autoaplicación por campo de Enrich v2.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from db.models import (
    CanonicalEnrichmentJob,
    CanonicalEnrichmentSource,
    CanonicalProduct,
)
from services.jobs.enrichment_jobs import (
    _build_result,
    _parse_json_response,
    _persist_sources,
    _safe_error_message,
)
from sqlalchemy.exc import IntegrityError


def _product() -> CanonicalProduct:
    return CanonicalProduct(id=1, name="Fertilizante Bloom", brand="Marca Uno", ng_sku="NG-000001")


def test_autoapplies_description_with_two_independent_domains(monkeypatch):
    monkeypatch.setenv("ENRICH_AUTO_APPLY_ENABLED", "1")
    monkeypatch.setenv("ENRICH_MIN_INDEPENDENT_SOURCES", "2")
    sources = [
        {"url": "https://fuente-a.example/ficha", "source_type": "web"},
        {"url": "https://fuente-b.example/manual", "source_type": "web"},
    ]
    generated = {
        "description_text": "Descripción respaldada.",
        "description_confidence": 0.94,
        "technical": {},
    }
    result, automatic = _build_result(_product(), generated, sources, "description")
    assert result["proposal"]["description_html"] == "<p>Descripción respaldada.</p>"
    assert automatic == ["description_html"]


def test_numeric_field_requires_explicit_known_source(monkeypatch):
    monkeypatch.setenv("ENRICH_AUTO_APPLY_ENABLED", "1")
    sources = [{"url": "https://fabricante.example/manual", "source_type": "official_manual"}]
    generated = {
        "technical": {
            "weight_kg": {"value": 1.5, "confidence": 0.99, "source_url": None},
            "height_cm": {
                "value": 20,
                "confidence": 0.95,
                "source_url": "https://fabricante.example/manual",
            },
        }
    }
    result, automatic = _build_result(_product(), generated, sources, "technical")
    assert "weight_kg" not in result["proposal"]
    assert result["proposal"]["height_cm"] == 20
    assert automatic == ["height_cm"]


def test_echo_fallback_is_never_valid():
    prompt = "Esquema de salida EXACTO: {}"
    with pytest.raises(RuntimeError, match="no produjo"):
        _parse_json_response(prompt, prompt)
    with pytest.raises(RuntimeError, match="no produjo"):
        _parse_json_response(f"ollama:{prompt}", prompt)


def test_valid_json_schema_is_accepted():
    payload = {"description_text": "Contenido", "description_confidence": 0.9, "technical": {}}
    assert _parse_json_response(json.dumps(payload), "prompt") == payload


@pytest.mark.asyncio
async def test_source_persistence_is_idempotent_between_retries(db_session):
    canonical = CanonicalProduct(name="CanÃ³nico", ng_sku="NG-ENRICH-RETRY")
    db_session.add(canonical)
    await db_session.flush()
    job = CanonicalEnrichmentJob(
        id="retry-source-job",
        canonical_product_id=canonical.id,
        client_request_id="retry-source-request",
        scope="description",
    )
    db_session.add(job)
    await db_session.commit()
    sources = [
        {
            "url": "https://example.com/manual",
            "title": "Manual",
            "source_type": "official_manual",
            "mime_type": "text/html",
            "content_hash": "abc",
            "snippet": "Evidencia",
            "text": "Contenido breve",
        }
    ]
    await _persist_sources(job, sources, db_session)
    await db_session.commit()
    await _persist_sources(job, sources, db_session)
    await db_session.commit()
    persisted = (
        await db_session.scalars(
            select(CanonicalEnrichmentSource).where(
                CanonicalEnrichmentSource.job_id == job.id
            )
        )
    ).all()
    assert len(persisted) == 1


def test_integrity_errors_do_not_persist_sql_parameters():
    error = IntegrityError(
        "insert",
        {"evidence": "contenido que no debe persistirse"},
        RuntimeError("duplicate"),
    )
    message = _safe_error_message(error)
    assert message == "Error de integridad al persistir el job"
    assert "evidence" not in message
