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
from db.models import Product, Supplier, SupplierProduct, ProductEquivalence, CanonicalProduct

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
        await s.commit()
        return {
            "product_id": p.id,
            "canonical_name": cp.name,
            "internal_name": p.title,
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
