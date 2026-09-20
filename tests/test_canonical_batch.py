#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_batch.py
# NG-HEADER: Ubicación: tests/test_canonical_batch.py
# NG-HEADER: Descripción: Pruebas del alta masiva canónica persistente y parcial.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

os.environ.setdefault("RUN_INLINE_JOBS", "1")

from db.models import CanonicalBatchJob, CanonicalBatchJobItem, CanonicalProduct, Category, Product, ProductTag, Supplier, SupplierProduct, Tag
from services.api import app
from services.auth import SessionData, current_session, require_csrf

app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def test_catalog_worker_emits_structured_stdout(capsys) -> None:
    from services.jobs.catalog_jobs import _log_catalog_event

    _log_catalog_event("job_finished", job_id="batch-test", success_count=2, error_count=0)
    event = json.loads(capsys.readouterr().out)

    assert event["service"] == "catalog_worker"
    assert event["event"] == "job_finished"
    assert event["job_id"] == "batch-test"
    assert event["success_count"] == 2


async def _source(db, prefix: str) -> tuple[Category, Category, SupplierProduct]:
    category = Category(name=f"{prefix}Root", parent_id=None, kind="category")
    db.add(category)
    await db.flush()
    subcategory = Category(name=f"{prefix}Sub", parent_id=category.id, kind="subcategory")
    supplier = Supplier(name=f"{prefix} Supplier", slug=f"{prefix.lower()}-supplier")
    product = Product(sku_root=f"{prefix}-ROOT", title=f"{prefix} interno")
    db.add_all([subcategory, supplier, product])
    await db.flush()
    source = SupplierProduct(
        supplier_id=supplier.id,
        supplier_product_id=f"{prefix}-SKU",
        title=f"{prefix} origen",
        internal_product_id=product.id,
    )
    db.add(source)
    await db.commit()
    return category, subcategory, source


async def _post(payload: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/canonical-products/batch-job", json=payload)


@pytest.mark.asyncio
async def test_batch_job_persists_progress_and_result(db_session) -> None:
    category, subcategory, source = await _source(db_session, "Bch")
    response = await _post({
        "client_request_id": "batch-success-1",
        "items": [{
            "name": "Producto Batch",
            "brand": "Growen",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "source_product_id": source.id,
        }],
    })
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status = await client.get(f"/canonical-products/batch-jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "COMPLETED"
    assert body["success_count"] == 1
    assert __import__("re").fullmatch(r"BCH_[0-9]{4}_[A-Z0-9]{3}", body["items"][0]["sku_custom"])


@pytest.mark.asyncio
async def test_batch_job_is_idempotent(db_session) -> None:
    category, subcategory, source = await _source(db_session, "Idm")
    payload = {
        "client_request_id": "same-client-request",
        "items": [{
            "name": "Producto único",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "source_product_id": source.id,
        }],
    }
    first = await _post(payload)
    second = await _post(payload)
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert await db_session.scalar(select(func.count(CanonicalProduct.id))) == 1
    assert await db_session.scalar(select(func.count(CanonicalBatchJob.id))) == 1


@pytest.mark.asyncio
async def test_failed_unprocessed_batch_is_requeued_with_same_idempotency_key(db_session, monkeypatch) -> None:
    category, subcategory, source = await _source(db_session, "Rty")
    job = CanonicalBatchJob(
        id="batch-canon-retry",
        client_request_id="retry-same-request",
        status="FAILED",
        total_items=1,
        error_message="Redis no disponible",
    )
    db_session.add(job)
    db_session.add(CanonicalBatchJobItem(
        job_id=job.id,
        position=0,
        source_product_id=source.id,
        name="Producto recuperable",
        category_id=category.id,
        subcategory_id=subcategory.id,
    ))
    await db_session.commit()

    from services.jobs.catalog_jobs import process_canonical_batch

    sent: list[str] = []
    monkeypatch.setenv("RUN_INLINE_JOBS", "0")
    monkeypatch.setattr(process_canonical_batch, "send", sent.append)
    response = await _post({
        "client_request_id": "retry-same-request",
        "items": [{
            "name": "Producto recuperable",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "source_product_id": source.id,
        }],
    })

    assert response.status_code == 202, response.text
    assert response.json()["message"] == "El lote fallido fue reenviado"
    assert sent == [job.id]
    await db_session.refresh(job)
    assert job.status == "QUEUED"
    assert job.error_message is None


@pytest.mark.asyncio
async def test_invalid_taxonomy_type_is_reported_as_error(db_session) -> None:
    category, _subcategory, source = await _source(db_session, "Bad")
    other = Category(name="OtherRoot", parent_id=None, kind="category")
    db_session.add(other)
    await db_session.flush()
    foreign_sub = Category(name="ForeignSub", parent_id=other.id, kind="category")
    db_session.add(foreign_sub)
    await db_session.commit()
    response = await _post({
        "client_request_id": "invalid-taxonomy",
        "items": [{
            "name": "Taxonomía inválida",
            "category_id": category.id,
            "subcategory_id": foreign_sub.id,
            "source_product_id": source.id,
        }],
    })
    job = await db_session.get(CanonicalBatchJob, response.json()["job_id"])
    await db_session.refresh(job, ["items"])
    assert job.status == "FAILED"
    assert job.items[0].error_code == "invalid_subcategory"


@pytest.mark.asyncio
async def test_batch_combines_persisted_tags_without_duplicate_relations(db_session) -> None:
    category, subcategory, source = await _source(db_session, "Tag")
    payload = {
        "client_request_id": "batch-tags-1",
        "items": [{
            "name": "Producto con tags",
            "category_id": category.id,
            "subcategory_id": subcategory.id,
            "tag_names": ["Interior", " interior ", "Orgánico"],
            "source_product_id": source.id,
        }],
    }
    response = await _post(payload)
    assert response.status_code == 202, response.text
    assert await db_session.scalar(select(func.count(Tag.id))) == 2
    assert await db_session.scalar(select(func.count(ProductTag.product_id))) == 2
    job = await db_session.get(CanonicalBatchJob, response.json()["job_id"])
    await db_session.refresh(job, ["items"])
    assert job.items[0].tag_names == ["Interior", " interior ", "Orgánico"]


@pytest.mark.asyncio
async def test_one_error_does_not_cancel_valid_items(db_session) -> None:
    category, subcategory, source = await _source(db_session, "Par")
    supplier = await db_session.get(Supplier, source.supplier_id)
    second = SupplierProduct(supplier_id=supplier.id, supplier_product_id="PAR-2", title="Segundo")
    db_session.add(second)
    await db_session.commit()
    response = await _post({
        "client_request_id": "partial-batch",
        "items": [
            {"name": "Válido", "category_id": category.id, "subcategory_id": subcategory.id, "source_product_id": source.id},
            {"name": "", "category_id": category.id, "subcategory_id": subcategory.id, "source_product_id": second.id},
        ],
    })
    job = await db_session.get(CanonicalBatchJob, response.json()["job_id"])
    assert job.status == "PARTIAL"
    assert job.success_count == 1 and job.error_count == 1


@pytest.mark.asyncio
async def test_batch_rejects_empty_and_over_limit() -> None:
    empty = await _post({"items": []})
    too_many = await _post({"items": [{"name": str(i)} for i in range(101)]})
    assert empty.status_code == 400
    assert too_many.status_code == 400


@pytest.mark.asyncio
async def test_batch_requires_staff_role() -> None:
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "guest")
    try:
        response = await _post({"items": [{"name": "Sin permiso"}]})
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
