#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_products_delete_rules.py
# NG-HEADER: Ubicación: tests/test_products_delete_rules.py
# NG-HEADER: Descripción: Pruebas para reglas de borrado de productos y respuestas
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")

from services.api import app  # noqa: E402

client = TestClient(app)


def test_delete_product_blocked_by_stock(monkeypatch):
    # Crear proveedor y producto
    import uuid
    su = uuid.uuid4().hex[:6]
    r = client.post("/suppliers", json={"slug": f"deltest-{su}", "name": f"Del Test {su}"})
    assert r.status_code in (200, 201)
    sup_id = r.json()["id"] if isinstance(r.json(), dict) else client.get("/suppliers").json()[0]["id"]

    prod = client.post(
        "/catalog/products",
        json={
            "title": "Prod X",
            "initial_stock": 5,
            "supplier_id": sup_id,
            "supplier_sku": f"SKU1-{su}",
            "sku": f"INTPX-{su}",
            "purchase_price": 1.0,
            "sale_price": 2.0,
        },
        headers={"X-CSRF-Token": "x"},
    )
    assert prod.status_code in (200, 201)
    pid = prod.json()["id"]

    # Intentar borrar (single) => 400
    resp = client.request("DELETE", "/catalog/products", json={"ids": [pid]}, headers={"X-CSRF-Token": "x"})
    assert resp.status_code == 400


def test_delete_product_blocked_by_purchase_refs(monkeypatch):
    # Crear proveedor y producto sin stock
    import uuid
    su = uuid.uuid4().hex[:6]
    r = client.post("/suppliers", json={"slug": f"deltest2-{su}", "name": f"Del Test 2 {su}"})
    assert r.status_code in (200, 201)
    sup_id = r.json()["id"] if isinstance(r.json(), dict) else client.get("/suppliers").json()[0]["id"]

    prod = client.post(
        "/catalog/products",
        json={
            "title": "Prod Y",
            "initial_stock": 0,
            "supplier_id": sup_id,
            "supplier_sku": f"SKU2-{su}",
            "sku": f"INTPY-{su}",
            "purchase_price": 1.0,
            "sale_price": 2.0,
        },
        headers={"X-CSRF-Token": "x"},
    )
    assert prod.status_code in (200, 201)
    pid = prod.json()["id"]

    # Crear compra con línea referenciando el producto
    p = client.post("/purchases", json={"supplier_id": sup_id, "remito_number": "R1", "remito_date": "2025-09-01"})
    assert p.status_code in (200, 201)
    purchase_id = p.json()["id"]
    upd = client.put(f"/purchases/{purchase_id}", json={"lines": [{"title": "X", "qty": 1, "unit_cost": 10, "product_id": pid}]})
    assert upd.status_code in (200, 201)

    # Intentar borrar => 409
    resp = client.request("DELETE", "/catalog/products", json={"ids": [pid]}, headers={"X-CSRF-Token": "x"})
    assert resp.status_code == 409


def test_delete_product_success(monkeypatch):
    import uuid
    su = uuid.uuid4().hex[:6]
    r = client.post("/suppliers", json={"slug": f"deltest3-{su}", "name": f"Del Test 3 {su}"})
    assert r.status_code in (200, 201)
    sup_id = r.json()["id"]
    prod = client.post(
        "/catalog/products",
        json={
            "title": "Prod Z",
            "initial_stock": 0,
            "supplier_id": sup_id,
            "supplier_sku": f"SKU3-{su}",
            "sku": f"INTPZ-{su}",
            "purchase_price": 1.0,
            "sale_price": 2.0,
        },
        headers={"X-CSRF-Token": "x"},
    )
    assert prod.status_code in (200, 201)
    pid = prod.json()["id"]
    resp = client.request("DELETE", "/catalog/products", json={"ids": [pid]}, headers={"X-CSRF-Token": "x"})
    assert resp.status_code == 200
    data = resp.json()
    assert pid in data.get("deleted", [])
