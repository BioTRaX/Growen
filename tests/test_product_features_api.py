#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_product_features_api.py
# NG-HEADER: Ubicación: tests/test_product_features_api.py
# NG-HEADER: Descripción: Tests para funcionalidades de productos (categorías inline y precios).
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
from httpx import AsyncClient
from services.api import app
from services.auth import current_session, require_csrf, SessionData
from db.session import get_session

pytestmark = pytest.mark.asyncio

async def _mock_user_session():
    return SessionData(None, None, "admin")

app.dependency_overrides[current_session] = _mock_user_session
app.dependency_overrides[require_csrf] = lambda: None
app.dependency_overrides[get_session] = get_session  # usar implementación real (memoria en tests)


async def test_create_product_with_new_inline_category():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/products",
            json={
                "title": "Fertilizante Orgánico",
                "initial_stock": 10,
                "new_category_name": "Fertilizantes",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category_id"] is not None
        cat_list = await client.get("/categories")
        assert cat_list.status_code == 200
        cats = cat_list.json()
        assert any(c["name"] == "Fertilizantes" and c["id"] == data["category_id"] for c in cats)


async def test_create_product_with_new_inline_subcategory():
    async with AsyncClient(app=app, base_url="http://test") as client:
        parent_resp = await client.post("/categories", json={"name": "Nutrientes"})
        assert parent_resp.status_code in (200, 409)
        if parent_resp.status_code == 200:
            parent_id = parent_resp.json()["id"]
        else:
            cats = (await client.get("/categories")).json()
            parent_id = next(c["id"] for c in cats if c["name"] == "Nutrientes" and c["parent_id"] is None)

        prod_resp = await client.post(
            "/products",
            json={
                "title": "Booster de Floración",
                "initial_stock": 5,
                "new_category_name": "Boosters",
                "new_category_parent_id": parent_id,
            },
        )
        assert prod_resp.status_code == 200
        pdata = prod_resp.json()
        cat_list = (await client.get("/categories")).json()
        new_cat = next(c for c in cat_list if c["id"] == pdata["category_id"])
        assert new_cat["name"] == "Boosters"
        assert new_cat["parent_id"] == parent_id
        assert new_cat["path"].endswith("Nutrientes>Boosters") or new_cat["path"] == "Nutrientes>Boosters"


async def test_update_prices():
    from db.models import CanonicalProduct, ProductEquivalence

    async with AsyncClient(app=app, base_url="http://test") as client:
        sup_resp = await client.post("/suppliers", json={"slug": "test-sup", "name": "Test Supplier"})
        assert sup_resp.status_code in (200, 409)
        if sup_resp.status_code == 200:
            supplier_id = sup_resp.json()["id"]
        else:
            supplier_id = (await client.get("/suppliers")).json()[0]["id"]

        import uuid as _uuid
        _uniq = _uuid.uuid4().hex[:6]
        prod_resp = await client.post(
            "/catalog/products",
            json={
                "title": f"Producto de Prueba Precios {_uniq}",
                "initial_stock": 0,
                "supplier_id": supplier_id,
                "supplier_sku": f"SKU123-{_uniq}",
                "sku": f"INTSKU-{_uniq}",
                "purchase_price": 10.0,
                "sale_price": 20.0,
            },
        )
        assert prod_resp.status_code == 200
        product_id = prod_resp.json()["id"]
        # Obtener SupplierProduct id real mediante consulta directa
        from sqlalchemy import select
        from db.models import SupplierProduct as _SP
        supplier_product_id = None
        async for s in get_session():
            supplier_product_id = (await s.scalar(select(_SP.id).where(_SP.internal_product_id == product_id)))
            break
        assert supplier_product_id, "No se pudo resolver supplier_product_id"

        patch_purchase = await client.patch(
            f"/products/{product_id}/prices",
            json={"supplier_item_id": supplier_product_id, "purchase_price": 99.99},
        )
        assert patch_purchase.status_code == 200
        assert patch_purchase.json()["updated_fields"]["purchase_price"] == 99.99

        # Crear canonical product y equivalencia directa
        async for s in get_session():
            cp = CanonicalProduct(name="Producto Canonico para Precio", sale_price=150.0)
            s.add(cp)
            await s.flush()
            eq = ProductEquivalence(
                supplier_id=supplier_id,
                supplier_product_id=supplier_product_id,
                canonical_product_id=cp.id,
                confidence=1.0,
                source="test",
            )
            s.add(eq)
            await s.commit()
            cp_id = cp.id
            break

        patch_sale = await client.patch(
            f"/products/{product_id}/prices",
            json={"supplier_item_id": supplier_product_id, "sale_price": 199.99},
        )
        assert patch_sale.status_code == 200
        assert float(patch_sale.json()["updated_fields"]["sale_price"]) == 199.99

        # Verificar cambio
        async for s in get_session():
            refreshed = await s.get(CanonicalProduct, cp_id)
            assert float(refreshed.sale_price) == 199.99
            break
