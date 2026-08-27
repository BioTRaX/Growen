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
from ai.providers.ollama_provider import OllamaUnavailableError
from services.jobs.enrichment_jobs import (
    EnrichmentProvidersError,
    ProviderResponseError,
    _build_result,
    _generate_with_provider,
    _compose_prompt,
    _parse_json_response,
    _persist_sources,
    _provider_diagnostic,
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


@pytest.mark.parametrize(
    "description",
    [
        "Maceta de plástico según la fuente.",
        "Las fuentes describen resistencia a impactos.",
        "Se reporta un diseño liviano y reutilizable.",
    ],
)
def test_description_with_research_metadiscourse_is_rejected(description):
    payload = {
        "description_text": description,
        "description_confidence": 0.95,
        "technical": {},
    }

    with pytest.raises(ProviderResponseError, match="proceso de investigación"):
        _parse_json_response(json.dumps(payload), "prompt")


def test_prompt_requires_publishable_description_without_source_metadiscourse():
    prompt = _compose_prompt(
        _product(),
        [{"url": "https://example.com", "title": "Ficha", "text": "Resistente a impactos"}],
        "full",
    )

    assert "voz activa" in prompt
    assert "Nunca menciones la investigación" in prompt
    assert "La descripción debe poder publicarse tal cual" in prompt
    assert "no incluyas source_note" in prompt
    assert "tono informal moderado" in prompt


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


def test_openai_diagnostic_keeps_safe_rate_limit_metadata():
    class Response:
        headers = {
            "x-request-id": "req_test_123",
            "x-ratelimit-remaining-requests": "0",
            "x-ratelimit-reset-requests": "2s",
            "authorization": "secret-that-must-not-leak",
        }

    class RateLimitError(RuntimeError):
        status_code = 429
        request_id = "req_test_123"
        body = {"error": {"code": "insufficient_quota", "message": "sensitive"}}
        response = Response()

    wrapped = RuntimeError("openai_request_failed")
    wrapped.__cause__ = RateLimitError("remote body")
    diagnostic = _provider_diagnostic(
        "openai",
        "gpt-4.1-mini",
        wrapped,
        job_attempt=2,
        client_request_id="growen-enrich-job-2-openai",
    )

    assert diagnostic["code"] == "insufficient_quota"
    assert diagnostic["http_status"] == 429
    assert diagnostic["request_id"] == "req_test_123"
    assert diagnostic["retryable"] is False
    assert diagnostic["rate_limits"] == {
        "remaining_requests": "0",
        "reset_requests": "2s",
    }
    assert "authorization" not in json.dumps(diagnostic)
    assert "sensitive" not in json.dumps(diagnostic)


def test_openai_credit_exhausted_is_not_retryable():
    error = ProviderResponseError(
        "credit_balance_exhausted", "El saldo del proveedor está agotado"
    )

    diagnostic = _provider_diagnostic(
        "openai",
        "gpt-5.6-luna",
        error,
        job_attempt=1,
        client_request_id="growen-enrich-job-1-openai",
    )

    assert diagnostic["code"] == "credit_balance_exhausted"
    assert diagnostic["retryable"] is False
    assert EnrichmentProvidersError([diagnostic]).retryable is False


@pytest.mark.asyncio
async def test_auto_mode_reports_openai_and_ollama_codes(monkeypatch):
    class FakeOpenAI:
        api_key = "configured"
        model = ""

        async def generate_async(self, *_args, **_kwargs):
            raise RuntimeError("openai_request_failed")

    class FakeOllama:
        model = ""

        def generate(self, _prompt):
            yield "not-json"

    monkeypatch.setenv("ENRICH_AI_MODE", "auto")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.test")
    monkeypatch.setattr("services.jobs.enrichment_jobs.OpenAIProvider", FakeOpenAI)
    monkeypatch.setattr("services.jobs.enrichment_jobs.OllamaProvider", FakeOllama)

    with pytest.raises(EnrichmentProvidersError) as failure:
        await _generate_with_provider("prompt", job_id="job-test", job_attempt=1)

    assert [item["code"] for item in failure.value.diagnostics] == [
        "provider_error",
        "invalid_json",
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OllamaUnavailableError("timeout"), "timeout"),
        (OllamaUnavailableError("http_error", http_status=503), "http_error"),
        (OllamaUnavailableError("ollama_empty_response"), "empty_response"),
        (ProviderResponseError("schema_invalid", "schema"), "schema_invalid"),
    ],
)
def test_ollama_diagnostic_taxonomy(error, expected):
    diagnostic = _provider_diagnostic(
        "ollama",
        "llama3.1:8b",
        error,
        job_attempt=1,
        client_request_id="growen-enrich-job-1-ollama",
    )

    assert diagnostic["code"] == expected
