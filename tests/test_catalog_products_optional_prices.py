#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_products_optional_prices.py
# NG-HEADER: Ubicación: tests/test_catalog_products_optional_prices.py
# NG-HEADER: Descripción: Pruebas de creación mínima de productos con precios opcionales y duplicados
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import uuid
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")

from services.api import app  # noqa: E402

client = TestClient(app)


def _ensure_supplier() -> int:
    su = uuid.uuid4().hex[:6]
    r = client.post("/suppliers", json={"slug": f"sup-{su}", "name": f"Sup {su}"})
    assert r.status_code in (200, 201, 409)
    if r.status_code in (200, 201):
        return r.json()["id"]
    # Si existe, traer cualquiera
    ls = client.get("/suppliers").json()
    assert isinstance(ls, list) and len(ls) > 0
    return ls[0]["id"]


def test_create_minimal_product_without_prices_ok_and_no_history():
    sup_id = _ensure_supplier()
    uniq = uuid.uuid4().hex[:6]
    # Generar SKU canónico válido: PRD_<4dig>_A<2hex>
    canonical_num = int(uniq[:4], 16) % 9999
    canonical_sku = f"PRD_{canonical_num:04d}_A{uniq[:2].upper()}"
    payload = {
        "title": f"Prod sin precios {uniq}",
        "initial_stock": 0,
        "supplier_id": sup_id,
    "supplier_sku": f"SP-{uniq}",
    "sku": canonical_sku,
        # precios omitidos
    }
    r = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert "id" in data and "sku_root" in data

    # Consultar historial de precios por product_id debe ser 200 y con 0 items
    ph = client.get("/price-history", params={"product_id": data["id"]})
    assert ph.status_code == 200, ph.text
    ph_data = ph.json()
    assert ph_data["total"] == 0
    assert isinstance(ph_data.get("items", []), list)
    assert len(ph_data["items"]) == 0


def test_create_minimal_product_duplicate_sku_conflict():
    sup_id = _ensure_supplier()
    uniq = uuid.uuid4().hex[:6]
    canonical_num = int(uniq[:4], 16) % 9999
    canonical_sku = f"PRD_{canonical_num:04d}_B{uniq[:2].upper()}"
    payload = {
        "title": f"Prod dup {uniq}",
        "initial_stock": 0,
        "supplier_id": sup_id,
    "supplier_sku": f"SP-{uniq}",
    "sku": canonical_sku,
        # precios omitidos, no requeridos
    }
    r1 = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
    assert r1.status_code in (200, 201), r1.text
    r2 = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
    # Puede devolver nuestro 409 directo o el handler de IntegrityError mapeado
    assert r2.status_code == 409, r2.text
    body = r2.json()
    # Aceptar cualquiera de los formatos esperados
    if isinstance(body.get("detail"), dict):
        assert body["detail"].get("code") == "duplicate_sku"
    else:
        # Fallback: handler global devuelve {code, detail}
        assert body.get("code") == "duplicate_sku" or "SKU ya existente" in body.get("detail", "")


def test_create_minimal_product_with_prices_history_created():
    sup_id = _ensure_supplier()
    uniq = uuid.uuid4().hex[:6]
    canonical_num = int(uniq[:4], 16) % 9999
    canonical_sku = f"PRD_{canonical_num:04d}_C{uniq[:2].upper()}"
    purchase = 123.45
    sale = 199.99
    payload = {
        "title": f"Prod con precios {uniq}",
        "initial_stock": 0,
        "supplier_id": sup_id,
    "supplier_sku": f"SP-{uniq}",
    "sku": canonical_sku,
        "purchase_price": purchase,
        "sale_price": sale,
    }
    r = client.post("/catalog/products", json=payload, headers={"X-CSRF-Token": "x"})
    assert r.status_code in (200, 201), r.text
    data = r.json()

    # Debe existir al menos un registro de historial de precios para ese producto
    ph = client.get("/price-history", params={"product_id": data["id"]})
    assert ph.status_code == 200, ph.text
    ph_data = ph.json()
    assert ph_data["total"] >= 1
    items = ph_data.get("items", [])
    assert isinstance(items, list) and len(items) >= 1
    # Verificar que haya un item que coincida con los precios enviados
    assert any(
        (
            (itm.get("purchase_price") is not None and abs(float(itm.get("purchase_price")) - purchase) < 1e-6)
            and (itm.get("sale_price") is not None and abs(float(itm.get("sale_price")) - sale) < 1e-6)
        )
        for itm in items
    )
