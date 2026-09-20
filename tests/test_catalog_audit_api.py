#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_audit_api.py
# NG-HEADER: Ubicación: tests/test_catalog_audit_api.py
# NG-HEADER: Descripción: Contrato HTTP, roles e idempotencia del auditor de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from db.models import (
    CanonicalContentVersion,
    CanonicalEnrichmentJob,
    CanonicalProduct,
    CatalogAuditItem,
    CatalogAuditFeedback,
    CatalogAuditRun,
    Product,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
    User,
)
from services.api import app
from services.auth import hash_pw
from services.routers import catalog_audits as catalog_audits_router


@pytest.mark.asyncio
async def test_admin_inicia_run_seleccionado_y_recibe_202(client_admin, db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Maceta Soplada 20L", content_revision=1)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    sent: list[str] = []
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", sent.append)
    monkeypatch.setattr("services.routers.catalog_audits._catalog_audit_preflight", _healthy_preflight)

    response = await client_admin.post("/canonical-products/catalog-audits", json={
        "scope": "selected", "canonical_product_ids": [product.id, product.id],
        "include_orphans": False, "mode": "deterministic_only", "enrich_missing": False, "auto_fix": False,
    })

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["status_url"].endswith(body["run_id"])
    assert sent == [body["run_id"]]


@pytest.mark.asyncio
async def test_colaborador_no_puede_habilitar_autocorreccion(client_collab) -> None:
    response = await client_collab.post("/canonical-products/catalog-audits", json={
        "scope": "all", "include_orphans": True, "mode": "full", "enrich_missing": True, "auto_fix": True,
    })

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_segundo_run_activo_responde_409(client_admin, db_session, monkeypatch) -> None:
    db_session.add(CanonicalProduct(name="Producto con contenido", description_html="<p>Contenido</p>"))
    await db_session.commit()
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", lambda _run_id: None)
    monkeypatch.setattr("services.routers.catalog_audits._catalog_audit_preflight", _healthy_preflight)
    payload = {"scope": "all", "include_orphans": False, "mode": "full", "enrich_missing": False, "auto_fix": False}

    assert (await client_admin.post("/canonical-products/catalog-audits", json=payload)).status_code == 202
    duplicate = await client_admin.post("/canonical-products/catalog-audits", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "active_catalog_audit_exists"


@pytest.mark.asyncio
async def test_retry_descarta_job_enrich_fallido_para_permitir_un_nuevo_intento(
    client_admin, db_session, monkeypatch
) -> None:
    product = CanonicalProduct(name="Producto sin contenido")
    run = CatalogAuditRun(
        id="run-enrich-fallido", scope="selected", mode="full", include_orphans=False,
        enrich_missing=True, auto_fix=False, status="completed_with_issues", is_active_slot=False,
        total_items=1, processed_items=1, issue_items=1,
        error_code="worker_interrupted", error_message="Error anterior",
    )
    db_session.add_all([product, run])
    await db_session.flush()
    failed_job = CanonicalEnrichmentJob(
        id="enrich-fallido", canonical_product_id=product.id,
        client_request_id="audit:run-enrich-fallido:producto", scope="full", status="failed",
    )
    db_session.add(failed_job)
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="e" * 64, rules_version="catalog-audit-r1", feedback_version="0",
        status="failed", enrichment_job_id=failed_job.id, error_code="enrich_missing_content",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", lambda _run_id: None)

    response = await client_admin.post(f"/canonical-products/catalog-audits/{run.id}/retry")

    assert response.status_code == 202
    await db_session.refresh(item)
    await db_session.refresh(run)
    assert item.status == "pending"
    assert item.enrichment_job_id is None
    assert run.processed_items == 0
    assert run.clean_items == 0
    assert run.issue_items == 0
    assert run.error_code is None
    assert run.error_message is None


async def _healthy_preflight() -> dict:
    return {
        "ollama": {"ok": True, "model": "llama3.1:8b"},
        "worker": {"ok": True}, "enrichment_worker": {"ok": True}, "queue": "catalog_audit",
    }


@pytest.mark.asyncio
async def test_listado_del_auditor_no_es_capturado_como_id_canonico(client_admin, db_session) -> None:
    db_session.add(CatalogAuditRun(
        id="run-listado-visible", scope="selected", mode="deterministic_only",
        include_orphans=False, enrich_missing=False, auto_fix=False,
        status="completed", is_active_slot=False,
    ))
    await db_session.commit()

    response = await client_admin.get("/canonical-products/catalog-audits")

    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()["items"]] == ["run-listado-visible"]


@pytest.mark.asyncio
async def test_detalle_expone_nombre_y_ficha_interna_del_canonico(client_admin, db_session) -> None:
    product = Product(sku_root="MAC-20L", title="Maceta interna", stock=0)
    supplier = Supplier(slug="proveedor-auditor", name="Proveedor auditor")
    linked = CanonicalProduct(name="Maceta Soplada 20L")
    orphan = CanonicalProduct(name="Canónico sin ficha")
    run = CatalogAuditRun(
        id="run-nombre-y-ficha", scope="selected", mode="deterministic_only",
        include_orphans=False, enrich_missing=False, auto_fix=False,
        status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, supplier, linked, orphan, run])
    await db_session.flush()
    supplier_product = SupplierProduct(
        supplier_id=supplier.id, supplier_product_id="MAC-20L", title="Maceta del proveedor",
        internal_product_id=product.id,
    )
    db_session.add(supplier_product)
    await db_session.flush()
    db_session.add(ProductEquivalence(
        supplier_id=supplier.id, supplier_product_id=supplier_product.id,
        canonical_product_id=linked.id, source="test",
    ))
    db_session.add_all([
        CatalogAuditItem(
            run_id=run.id, canonical_product_id=linked.id, target_key=f"canonical:{linked.id}",
            input_hash="1" * 64, rules_version="catalog-audit-r1", feedback_version="0",
            status="clean",
        ),
        CatalogAuditItem(
            run_id=run.id, canonical_product_id=orphan.id, target_key=f"canonical:{orphan.id}",
            input_hash="2" * 64, rules_version="catalog-audit-r1", feedback_version="0",
            status="needs_review",
        ),
    ])
    await db_session.commit()

    response = await client_admin.get(f"/canonical-products/catalog-audits/{run.id}")

    assert response.status_code == 200
    items = {item["canonical_product_id"]: item for item in response.json()["items"]}
    assert items[linked.id]["canonical_name"] == "Maceta Soplada 20L"
    assert items[linked.id]["product_detail_id"] == product.id
    assert items[orphan.id]["canonical_name"] == "Canónico sin ficha"
    assert items[orphan.id]["product_detail_id"] is None


@pytest.mark.asyncio
async def test_resumen_operativo_expone_cola_runs_e_items(client_admin, db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Producto pendiente de auditoría")
    run = CatalogAuditRun(
        id="run-encolado-visible", scope="selected", mode="deterministic_only",
        include_orphans=False, enrich_missing=False, auto_fix=False,
        status="queued", is_active_slot=True,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    db_session.add(CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id,
        target_key=f"canonical:{product.id}", input_hash="d" * 64,
        rules_version="catalog-audit-r1", feedback_version="0", status="pending",
    ))
    await db_session.commit()
    monkeypatch.setattr(
        catalog_audits_router,
        "_catalog_audit_queue_status",
        lambda: {"broker_ok": True, "ready": 2, "delayed": 1},
        raising=False,
    )
    monkeypatch.setattr(
        catalog_audits_router,
        "_catalog_audit_runtime_status",
        lambda: {"status": "running", "ok": True, "pid": 4321, "detail": "heartbeat vigente"},
        raising=False,
    )

    response = await client_admin.get("/canonical-products/catalog-audits/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["worker"] == {
        "status": "running", "ok": True, "pid": 4321, "detail": "heartbeat vigente",
        "broker_ok": True, "ready": 2, "delayed": 1,
    }
    assert body["runs"]["active"] == 1
    assert body["runs"]["by_status"] == {"queued": 1}
    assert body["items"]["by_status"] == {"pending": 1}
    assert body["runs"]["recent"][0]["run_id"] == "run-encolado-visible"


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_inicio_real_exige_sesion_csrf_y_rol_admin_para_autofix(db_session, monkeypatch) -> None:
    admin = User(identifier="catalog-audit-admin", password_hash=hash_pw("segura-test-123"), role="admin")
    collaborator = User(identifier="catalog-audit-collab", password_hash=hash_pw("segura-test-123"), role="colaborador")
    admin_identifier = admin.identifier
    collaborator_identifier = collaborator.identifier
    db_session.add_all([admin, collaborator, CanonicalProduct(name="Producto auditable", description_html="<p>Ficha</p>")])
    await db_session.commit()
    monkeypatch.setattr("services.routers.catalog_audits._catalog_audit_preflight", _healthy_preflight)
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", lambda _run_id: None)
    payload = {"scope": "all", "include_orphans": False, "mode": "full", "enrich_missing": False, "auto_fix": True}

    with TestClient(app) as client:
        assert client.post("/canonical-products/catalog-audits", json=payload).status_code in {401, 403}
        assert client.post("/auth/login", json={"identifier": collaborator_identifier, "password": "segura-test-123"}).status_code == 200
        csrf = client.cookies.get("csrf_token")
        assert client.post("/canonical-products/catalog-audits", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 403

    with TestClient(app) as client:
        assert client.post("/auth/login", json={"identifier": admin_identifier, "password": "segura-test-123"}).status_code == 200
        assert client.post("/canonical-products/catalog-audits", json=payload).status_code == 403
        csrf = client.cookies.get("csrf_token")
        assert client.post("/canonical-products/catalog-audits", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 202


@pytest.mark.asyncio
async def test_reauditar_crea_run_nuevo_forzado_y_lo_encola(client_admin, db_session, monkeypatch) -> None:
    product = CanonicalProduct(name="Producto ya auditado", description_html="<p>Ficha suficiente</p>", content_revision=3)
    run = CatalogAuditRun(
        id="run-finalizado", scope="selected", mode="deterministic_only", include_orphans=False,
        enrich_missing=False, auto_fix=False, status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="a" * 64, rules_version="catalog-audit-r1", feedback_version="0",
        status="needs_review", product_class="other",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    sent: list[str] = []
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", sent.append)

    response = await client_admin.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={"action": "reaudit", "note": "Revisar con las reglas vigentes"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["new_run_id"] and body["new_run_id"] != run.id
    assert sent == [body["new_run_id"]]
    new_run = await db_session.get(CatalogAuditRun, body["new_run_id"])
    new_item = await db_session.scalar(select(CatalogAuditItem).where(CatalogAuditItem.run_id == new_run.id))
    assert new_run.requested_ids == [product.id]
    assert new_item.status == "pending"
    assert new_item.reused_item_id is None


@pytest.mark.asyncio
async def test_colaborador_no_puede_clasificar_item(client_collab, db_session) -> None:
    product = CanonicalProduct(name="Producto dudoso")
    run = CatalogAuditRun(
        id="run-colaborador", scope="selected", mode="deterministic_only", include_orphans=False,
        enrich_missing=False, auto_fix=False, status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="b" * 64, rules_version="catalog-audit-r1", feedback_version="0", status="needs_review",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    response = await client_collab.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={"action": "classification", "note": "Es un contenedor", "product_class": "container"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_colaborador_no_puede_aceptar_excepcion(client_collab, db_session) -> None:
    product = CanonicalProduct(name="Producto revisable")
    run = CatalogAuditRun(
        id="run-excepcion-colaborador", scope="selected", mode="deterministic_only",
        include_orphans=False, enrich_missing=False, auto_fix=False,
        status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="f" * 64, rules_version="catalog-audit-r1", feedback_version="0",
        status="needs_review",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    response = await client_collab.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={"action": "accept_exception", "note": "Producto revisado manualmente"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_acepta_excepcion_y_deja_feedback_trazable(client_admin, db_session) -> None:
    product = CanonicalProduct(name="Producto verificado", catalog_audit_status="needs_review")
    run = CatalogAuditRun(
        id="run-excepcion-admin", scope="selected", mode="deterministic_only",
        include_orphans=False, enrich_missing=False, auto_fix=False,
        status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="e" * 64, rules_version="catalog-audit-r1", feedback_version="0",
        status="needs_review",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    response = await client_admin.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={"action": "accept_exception", "note": "Producto verificado manualmente"},
    )

    assert response.status_code == 200
    await db_session.refresh(item)
    await db_session.refresh(product)
    feedback = await db_session.scalar(
        select(CatalogAuditFeedback).where(CatalogAuditFeedback.canonical_product_id == product.id)
    )
    assert item.status == "clean"
    assert item.resolution == "accept_exception"
    assert item.resolution_note == "Producto verificado manualmente"
    assert product.catalog_audit_status == "clean"
    assert feedback is not None
    assert feedback.kind == "exception"
    assert feedback.payload_json["note"] == "Producto verificado manualmente"


@pytest.mark.asyncio
async def test_correccion_manual_rechaza_campos_protegidos(client_admin, db_session) -> None:
    product = CanonicalProduct(name="Producto protegido", content_revision=2)
    run = CatalogAuditRun(
        id="run-protegido", scope="selected", mode="full", include_orphans=False,
        enrich_missing=False, auto_fix=False, status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="c" * 64, rules_version="catalog-audit-r1", feedback_version="0", status="needs_review",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    response = await client_admin.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={
            "action": "apply_correction", "note": "No debe alterar identidad",
            "expected_content_revision": 2, "corrections": {"name": "Nombre nuevo"},
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_correccion_manual_serializa_decimales_en_la_version(client_admin, db_session, monkeypatch) -> None:
    product = CanonicalProduct(
        name="Maceta medible", description_html="<p>Contenido original</p>",
        height_cm=Decimal("12.50"), content_revision=2,
    )
    run = CatalogAuditRun(
        id="run-version-decimal", scope="selected", mode="deterministic_only", include_orphans=False,
        enrich_missing=False, auto_fix=False, status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, run])
    await db_session.flush()
    item = CatalogAuditItem(
        run_id=run.id, canonical_product_id=product.id, target_key=f"canonical:{product.id}",
        input_hash="d" * 64, rules_version="catalog-audit-r1", feedback_version="0", status="needs_review",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    monkeypatch.setattr("services.routers.catalog_audits.process_catalog_audit_run.send", lambda _run_id: None)

    response = await client_admin.post(
        f"/canonical-products/catalog-audits/{run.id}/items/{item.id}/resolve",
        json={
            "action": "apply_correction", "note": "Corrección controlada con snapshot",
            "expected_content_revision": 2, "corrections": {"description_html": "<p>Contenido revisado</p>"},
        },
    )

    assert response.status_code == 200
    version = await db_session.scalar(
        select(CanonicalContentVersion).where(CanonicalContentVersion.canonical_product_id == product.id)
    )
    assert version is not None
    assert version.snapshot_json["height_cm"] == "12.50"
