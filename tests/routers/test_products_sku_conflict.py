import pytest
from httpx import AsyncClient
from services.api import app

pytestmark = pytest.mark.asyncio

async def test_create_minimal_product_and_duplicate_sku(monkeypatch):
    import uuid
    uniq = uuid.uuid4().hex[:6]
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Crear supplier
        rs = await ac.post("/suppliers", json={"slug": f"sku-sup-{uniq}", "name": f"Sup {uniq}"})
        assert rs.status_code in (200, 409)
        if rs.status_code == 200:
            sup_id = rs.json()["id"]
        else:
            sup_id = (await ac.get("/suppliers")).json()[0]["id"]
        base_payload = {
            "title": f"Producto SKU {uniq}",
            "initial_stock": 2,
            "supplier_id": sup_id,
            "supplier_sku": f"EXT-{uniq}",
            "sku": f"INT-{uniq}",
            "purchase_price": 10.5,
            "sale_price": 20.0,
        }
        r1 = await ac.post("/catalog/products", json=base_payload, headers={"X-CSRF-Token": "x"})
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert data1["sku_root"] == f"INT-{uniq}"
        # Reintento con mismo SKU
        r2 = await ac.post("/catalog/products", json=base_payload, headers={"X-CSRF-Token": "x"})
        assert r2.status_code == 409, r2.text
        err = r2.json()
        # Nuevo formato: {detail: {code, message}} o legacy directo (handler IntegrityError)
        if isinstance(err.get("detail"), dict):
            assert err["detail"].get("code") == "duplicate_sku"
        else:
            # fallback por si proviene del handler global
            assert err.get("code") == "duplicate_sku" or "SKU ya existente" in err.get("detail", "")
