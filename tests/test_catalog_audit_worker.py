#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_audit_worker.py
# NG-HEADER: Ubicación: tests/test_catalog_audit_worker.py
# NG-HEADER: Descripción: Ejecución, autocorrección segura y cierre del worker auditor.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from db.models import CanonicalEnrichmentJob, CanonicalProduct, CatalogAuditItem, CatalogAuditRun
from db.session import SessionLocal
from services.catalog_audit.repository import create_run_items
from services.jobs.catalog_audit_jobs import (
    _eligible_corrections,
    _recover_active_runs_async,
    _wait_for_enrich,
    process_catalog_audit_run_async,
)


@pytest.mark.skipif(os.name != "nt", reason="La regresión sólo afecta al loop de Windows")
def test_importar_worker_configura_selector_loop_para_psycopg() -> None:
    command = (
        "import asyncio; "
        "import services.jobs.catalog_audit_jobs; "
        "loop=asyncio.get_event_loop_policy().new_event_loop(); "
        "print(type(loop).__name__); loop.close()"
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        env={**os.environ, "CATALOG_AUDIT_HEARTBEAT_ENABLED": "0"},
    )

    assert "Selector" in result.stdout


def test_autocorreccion_excluye_identidad_dinero_y_fuente_unica() -> None:
    semantic = {"fields": [
        {"field": "sale_price", "proposed_value": 10, "confidence": 1, "sources": ["https://a.example/x", "https://b.example/x"]},
        {"field": "description_html", "proposed_value": "<p>x</p>", "confidence": .99, "sources": ["https://a.example/1", "https://a.example/2"]},
        {"field": "technical_specs", "proposed_value": {"material": "PP"}, "confidence": .97, "sources": ["https://a.example/1", "https://b.example/2"]},
    ]}

    assert [item["field"] for item in _eligible_corrections(semantic)] == ["technical_specs"]


@pytest.mark.asyncio
async def test_modo_determinista_no_marca_auditoria_completa(db_session) -> None:
    product = CanonicalProduct(name="Maceta Soplada 20L", description_html="<p>Maceta de cultivo.</p>")
    db_session.add(product)
    await db_session.flush()
    run = CatalogAuditRun(
        id="run-deterministic", scope="selected", mode="deterministic_only", status="queued",
        is_active_slot=True, include_orphans=False, enrich_missing=False,
    )
    db_session.add(run)
    await db_session.flush()
    items = await create_run_items(db_session, run, [product], include_orphans=False)
    run_id = run.id
    item_id = items[0].id
    await db_session.commit()

    await process_catalog_audit_run_async(run_id)
    db_session.expire_all()
    finished = await db_session.get(CatalogAuditRun, run_id)
    item = await db_session.get(CatalogAuditItem, item_id)

    assert finished is not None and finished.status == "completed_with_issues"
    assert finished.is_active_slot is False
    assert item is not None and item.status == "needs_review"
    assert item.error_code == "semantic_audit_skipped"


@pytest.mark.asyncio
async def test_estado_running_y_auditing_es_visible_mientras_ollama_trabaja(db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Maceta visible", description_html="<p>Ficha suficiente.</p>")
    run = CatalogAuditRun(
        id="run-visible-durante-ollama", scope="selected", mode="full", status="queued",
        is_active_slot=True, include_orphans=False, enrich_missing=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = (await create_run_items(db_session, run, [product], include_orphans=False))[0]
    run_id, item_id = run.id, item.id
    await db_session.commit()
    observed: dict[str, str] = {}

    class InspectingSemanticClient:
        async def audit(self, _payload) -> dict:
            async with SessionLocal() as probe:
                persisted_run = await probe.get(CatalogAuditRun, run_id)
                persisted_item = await probe.get(CatalogAuditItem, item_id)
                observed["run"] = persisted_run.status
                observed["item"] = persisted_item.status
            return {"classification": "container", "score": 90, "critical": False, "fields": []}

    monkeypatch.setattr(
        "services.jobs.catalog_audit_jobs.CatalogAuditOllamaClient",
        InspectingSemanticClient,
    )

    await process_catalog_audit_run_async(run_id)

    assert observed == {"run": "running", "item": "auditing"}


@pytest.mark.asyncio
async def test_contenido_ausente_crea_y_despacha_un_solo_enrich(db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Producto sin ficha")
    run = CatalogAuditRun(
        id="run-enrich-unico", scope="selected", mode="full", status="queued",
        is_active_slot=True, include_orphans=False, enrich_missing=True,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = (await create_run_items(db_session, run, [product], include_orphans=False))[0]
    dispatched: list[str] = []

    async def fake_dispatch(job, _session) -> None:
        dispatched.append(job.id)

    monkeypatch.setattr("services.jobs.catalog_audit_jobs.dispatch_enrichment_job", fake_dispatch)

    assert await _wait_for_enrich(run, item, product, db_session) is True
    assert await _wait_for_enrich(run, item, product, db_session) is True

    job = await db_session.get(CanonicalEnrichmentJob, item.enrichment_job_id)
    assert job is not None
    assert job.client_request_id == f"audit:{run.id[:16]}:{product.id}:1"
    assert dispatched == [job.id]


@pytest.mark.asyncio
async def test_retry_de_auditoria_crea_otro_enrich_si_el_anterior_fallo(db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Producto a reintentar")
    run = CatalogAuditRun(
        id="run-retry-enrich", scope="selected", mode="full", status="running",
        is_active_slot=True, include_orphans=False, enrich_missing=True,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    old_job = CanonicalEnrichmentJob(
        id="job-enrich-anterior", canonical_product_id=product.id,
        client_request_id=f"audit:{run.id[:16]}:{product.id}:1", batch_id=run.id,
        scope="full", status="failed",
    )
    db_session.add(old_job)
    await db_session.flush()
    item = (await create_run_items(db_session, run, [product], include_orphans=False))[0]
    dispatched: list[str] = []

    async def fake_dispatch(job, _session) -> None:
        dispatched.append(job.id)

    monkeypatch.setattr("services.jobs.catalog_audit_jobs.dispatch_enrichment_job", fake_dispatch)

    waiting = await _wait_for_enrich(run, item, product, db_session)

    assert waiting is True
    assert item.enrichment_job_id != old_job.id
    new_job = await db_session.get(CanonicalEnrichmentJob, item.enrichment_job_id)
    assert new_job.client_request_id == f"audit:{run.id[:16]}:{product.id}:2"
    assert dispatched == [item.enrichment_job_id]


@pytest.mark.asyncio
async def test_enrich_revisable_sin_campos_aplicados_queda_para_revision_manual(db_session) -> None:
    product = CanonicalProduct(name="Producto con evidencia insuficiente")
    run = CatalogAuditRun(
        id="run-enrich-revisable", scope="selected", mode="full", status="waiting_enrich",
        is_active_slot=True, include_orphans=False, enrich_missing=True,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    job = CanonicalEnrichmentJob(
        id="job-enrich-revisable", canonical_product_id=product.id,
        client_request_id="audit:revisable", scope="full", status="review_required",
        result_json={"proposal": {"description_html": "<p>Propuesta de baja confianza.</p>"}},
    )
    db_session.add(job)
    await db_session.flush()
    item = (await create_run_items(db_session, run, [product], include_orphans=False))[0]
    item.status = "waiting_enrich"
    item.enrichment_job_id = job.id

    waiting = await _wait_for_enrich(run, item, product, db_session)

    assert waiting is False
    assert item.status == "needs_review"
    assert item.error_code == "enrich_review_required"
    assert product.catalog_audit_status == "needs_review"
    assert product.catalog_audited_at is not None
    assert product.last_catalog_audit_item_id == item.id


@pytest.mark.asyncio
async def test_cancelacion_persistida_cierra_run_y_sus_items(db_session) -> None:
    product = CanonicalProduct(name="Producto cancelado", description_html="<p>Ficha</p>")
    run = CatalogAuditRun(
        id="run-cancelado", scope="selected", mode="full", status="queued",
        is_active_slot=True, include_orphans=False, enrich_missing=False, cancel_requested=True,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = (await create_run_items(db_session, run, [product], include_orphans=False))[0]
    run_id, item_id = run.id, item.id
    await db_session.commit()

    await process_catalog_audit_run_async(run_id)
    db_session.expire_all()

    finished = await db_session.get(CatalogAuditRun, run_id)
    cancelled_item = await db_session.get(CatalogAuditItem, item_id)
    assert finished.status == "cancelled"
    assert finished.is_active_slot is False
    assert cancelled_item.status == "cancelled"


@pytest.mark.asyncio
async def test_reinicio_del_worker_reencola_runs_activos(db_session, monkeypatch) -> None:
    active = CatalogAuditRun(
        id="run-a-recuperar", scope="all", mode="full", status="running", is_active_slot=True,
    )
    completed = CatalogAuditRun(
        id="run-ya-finalizado", scope="all", mode="full", status="completed", is_active_slot=False,
    )
    db_session.add_all([active, completed])
    await db_session.commit()
    sent: list[str] = []
    monkeypatch.setattr("services.jobs.catalog_audit_jobs.process_catalog_audit_run.send", sent.append)

    recovered = await _recover_active_runs_async()

    assert recovered == 1
    assert sent == [active.id]
