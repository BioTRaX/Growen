#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_audit_persistence.py
# NG-HEADER: Ubicación: tests/test_catalog_audit_persistence.py
# NG-HEADER: Descripción: Persistencia e idempotencia del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import CanonicalProduct, CatalogAuditFeedback, CatalogAuditItem, CatalogAuditRun
from services.catalog_audit.repository import RULESET_VERSION, create_run_items


@pytest.mark.asyncio
async def test_un_solo_run_global_activo(db_session) -> None:
    db_session.add(CatalogAuditRun(id="run-1", scope="all", mode="full", status="running"))
    await db_session.commit()
    db_session.add(CatalogAuditRun(id="run-2", scope="pending", mode="full", status="queued"))

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_producto_sin_cambios_se_registra_como_skipped(db_session) -> None:
    product = CanonicalProduct(name="Maceta 20L", brand="Growen", content_revision=1)
    db_session.add(product)
    await db_session.flush()
    previous_run = CatalogAuditRun(
        id="run-old", scope="all", mode="full", status="completed", is_active_slot=False
    )
    db_session.add(previous_run)
    await db_session.flush()
    await create_run_items(db_session, previous_run, [product], include_orphans=False)
    previous_item = await db_session.scalar(select(CatalogAuditItem).where(CatalogAuditItem.run_id == previous_run.id))
    assert previous_item is not None
    previous_item.status = "clean"
    previous_item.completed_at = previous_run.created_at
    await db_session.commit()

    current_run = CatalogAuditRun(id="run-new", scope="pending", mode="full", status="queued")
    db_session.add(current_run)
    await db_session.flush()
    await create_run_items(db_session, current_run, [product], include_orphans=False)
    current_item = await db_session.scalar(select(CatalogAuditItem).where(CatalogAuditItem.run_id == current_run.id))

    assert current_item is not None
    assert current_item.status == "skipped_unchanged"
    assert current_item.reused_item_id == previous_item.id
    assert current_item.rules_version == RULESET_VERSION


@pytest.mark.asyncio
async def test_hallazgo_sin_cambios_conserva_estado_y_evidencia(db_session) -> None:
    product = CanonicalProduct(name="Producto pendiente", description_html="<p>Ficha estable</p>")
    previous_run = CatalogAuditRun(
        id="run-issue-old", scope="all", mode="full", status="completed_with_issues", is_active_slot=False,
    )
    db_session.add_all([product, previous_run])
    await db_session.flush()
    previous_item = (await create_run_items(db_session, previous_run, [product], include_orphans=False))[0]
    previous_item.status = "needs_review"
    previous_item.product_class = "other"
    previous_item.score = 62
    previous_item.findings_json = {"warnings": ["Revisar descripción"]}
    previous_item.evidence_json = ["https://evidencia.example/ficha"]
    await db_session.commit()

    current_run = CatalogAuditRun(id="run-issue-new", scope="all", mode="full", status="queued")
    db_session.add(current_run)
    await db_session.flush()
    current_item = (await create_run_items(db_session, current_run, [product], include_orphans=False))[0]

    assert current_item.status == "needs_review"
    assert current_item.reused_item_id == previous_item.id
    assert current_item.product_class == "other"
    assert current_item.score == 62
    assert current_item.findings_json == previous_item.findings_json
    assert current_item.evidence_json == previous_item.evidence_json


@pytest.mark.asyncio
async def test_cambiar_solo_revision_no_repite_trabajo(db_session) -> None:
    product = CanonicalProduct(name="Carpa Indoor", description_html="<p>Ficha estable</p>", content_revision=1)
    old_run = CatalogAuditRun(id="run-revision-old", scope="all", mode="full", status="completed", is_active_slot=False)
    db_session.add_all([product, old_run])
    await db_session.flush()
    old_item = (await create_run_items(db_session, old_run, [product], include_orphans=False))[0]
    old_item.status = "clean"
    await db_session.commit()

    product.content_revision = 2
    new_run = CatalogAuditRun(id="run-revision-new", scope="pending", mode="full", status="queued")
    db_session.add(new_run)
    await db_session.flush()
    new_item = (await create_run_items(db_session, new_run, [product], include_orphans=False))[0]

    assert new_item.status == "skipped_unchanged"
    assert new_item.reused_item_id == old_item.id


@pytest.mark.asyncio
async def test_feedback_global_de_clase_invalida_solo_productos_aplicables(db_session) -> None:
    container = CanonicalProduct(name="Maceta Soplada 20L", description_html="<p>Maceta</p>")
    liquid = CanonicalProduct(name="Fertilizante líquido 1L", description_html="<p>Nutriente</p>")
    old_run = CatalogAuditRun(id="run-feedback-old", scope="all", mode="full", status="completed", is_active_slot=False)
    db_session.add_all([container, liquid, old_run])
    await db_session.flush()
    old_items = await create_run_items(db_session, old_run, [container, liquid], include_orphans=False)
    for item in old_items:
        item.status = "clean"
    await db_session.commit()

    db_session.add(CatalogAuditFeedback(
        canonical_product_id=None, product_class="container", kind="classification", version=1,
        payload_json={"note": "Regla exclusiva para contenedores"},
    ))
    new_run = CatalogAuditRun(id="run-feedback-new", scope="pending", mode="full", status="queued")
    db_session.add(new_run)
    await db_session.flush()
    new_items = await create_run_items(db_session, new_run, [container, liquid], include_orphans=False)
    by_product = {item.canonical_product_id: item for item in new_items}

    assert by_product[container.id].status == "pending"
    assert by_product[container.id].feedback_version == "1"
    assert by_product[liquid.id].status == "skipped_unchanged"
    assert by_product[liquid.id].feedback_version == "0"
