#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_products_sku_conflict.py
# NG-HEADER: Ubicación: tests/routers/test_products_sku_conflict.py
# NG-HEADER: Descripción: Prueba de conflicto de SKU duplicado (adaptada a formato canónico)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import uuid
import pytest
from httpx import AsyncClient
from services.api import app

pytestmark = pytest.mark.asyncio

@pytest.mark.legacy
async def test_create_minimal_product_and_duplicate_sku():
    """Caso heredado: originalmente usaba formato no canónico INT-xxxxx.

    Se actualiza para usar un SKU canónico válido mientras se mantiene la
    intención: crear un producto y verificar que un segundo POST con el mismo
    SKU genere conflicto duplicate_sku. Marcado como legacy porque el patrón
    definitivo para nuevos tests es generar dinámicamente SKUs o usar la
    generación automática por category/subcategory.
    """
    uniq = uuid.uuid4().hex[:6].upper()
    num = int(uniq[:4], 16) % 9999
    # Prefijo y sufijo derivados (simple) para mantener independencia entre ejecuciones
    prefix = "TST"  # categoría sintética de pruebas
    suffix = uniq[:3]
    canonical_sku = f"{prefix}_{num:04d}_{suffix}"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        rs = await ac.post("/suppliers", json={"slug": f"sku-sup-{uniq.lower()}", "name": f"Sup {uniq}"})
        assert rs.status_code in (200, 409)
        if rs.status_code in (200, 201):
            sup_id = rs.json()["id"]
        else:
            sup_id = (await ac.get("/suppliers")).json()[0]["id"]
        payload = {
            "title": f"Producto SKU {uniq}",
            "initial_stock": 2,
            "supplier_id": sup_id,
            "supplier_sku": f"EXT-{uniq}",
            "sku": canonical_sku,
            "purchase_price": 10.5,
            "sale_price": 20.0,
        }
        r1 = await ac.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
        assert r1.status_code in (200, 201), r1.text
        data1 = r1.json()
        assert data1["sku_root"] == canonical_sku
        # Reintento para provocar conflicto
        r2 = await ac.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
        assert r2.status_code == 409, r2.text
        err = r2.json()
        if isinstance(err.get("detail"), dict):
            assert err["detail"].get("code") == "duplicate_sku"
        else:
            assert err.get("code") == "duplicate_sku" or "SKU ya existente" in err.get("detail", "")
