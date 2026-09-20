#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_products_search_canonical.py
# NG-HEADER: Ubicación: tests/test_products_search_canonical.py
# NG-HEADER: Descripción: Tests de GET /products: búsqueda por nombre canónico y campos canónicos en payload.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest

# Entorno de pruebas en SQLite memoria
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("AUTH_ENABLED", "true")

from fastapi.testclient import TestClient

from services.api import app
from services.auth import current_session, require_csrf, SessionData
from db.models import (
    CanonicalProduct,
    CatalogAuditItem,
    CatalogAuditRun,
    Product,
    ProductEquivalence,
    Supplier,
    SupplierProduct,
)

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


async def _seed_minimal_with_canonical():
    from db.session import SessionLocal
    async with SessionLocal() as s:  # type: ignore
        sup = Supplier(slug="acme2", name="ACME 2")
        s.add(sup)
        await s.flush()
        p = Product(sku_root="SKU2", title="Producto Interno Z")
        s.add(p)
        await s.flush()
        sp = SupplierProduct(supplier_id=sup.id, supplier_product_id="Z1", title="Proveedor Z", internal_product_id=p.id)
        s.add(sp)
        await s.flush()
        cp = CanonicalProduct(name="Canónico Z Master", sku_custom="ZZZ_0002_XXX")
        s.add(cp)
        await s.flush()
        eq = ProductEquivalence(supplier_id=sup.id, supplier_product_id=sp.id, canonical_product_id=cp.id, source="test")
        s.add(eq)
        audit_run = CatalogAuditRun(
            id="run-products-search", scope="selected", mode="deterministic_only",
            include_orphans=False, enrich_missing=False, auto_fix=False,
            status="completed_with_issues", is_active_slot=False,
        )
        s.add(audit_run)
        await s.flush()
        audit_item = CatalogAuditItem(
            run_id=audit_run.id, canonical_product_id=cp.id, target_key=f"canonical:{cp.id}",
            input_hash="a" * 64, rules_version="catalog-audit-r1", feedback_version="0",
            status="needs_review",
        )
        s.add(audit_item)
        await s.flush()
        cp.catalog_audit_status = "needs_review"
        cp.last_catalog_audit_item_id = audit_item.id
        await s.commit()
        return {
            "product_id": p.id,
            "canonical_name": cp.name,
            "internal_name": p.title,
            "audit_item_id": audit_item.id,
            "audit_run_id": audit_run.id,
        }


@pytest.mark.asyncio
async def test_products_search_matches_canonical_name_and_includes_fields():
    seeded = await _seed_minimal_with_canonical()
    # Buscar por el nombre canónico
    r = client.get("/products", params={"q": seeded["canonical_name"]})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert data.get("total", 0) >= 1
    items = data.get("items", [])
    # Al menos uno debería tener canonical_name esperado y preferred_name igual al canónico
    found = None
    for it in items:
        if it.get("canonical_name") == seeded["canonical_name"]:
            found = it
            break
    assert found is not None, "No se encontró item con canonical_name esperado en /products"
    assert found.get("preferred_name") == seeded["canonical_name"], "preferred_name debe priorizar el título canónico"
    # name (interno) debe estar presente y puede diferir del canónico
    assert found.get("name") == seeded["internal_name"], "name corresponde al título interno de Product"
    assert found.get("catalog_audit_status") == "needs_review"
    assert found.get("catalog_audit_item_id") == seeded["audit_item_id"]
    assert found.get("catalog_audit_run_id") == seeded["audit_run_id"]
