#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_reports_new.py
# NG-HEADER: Ubicación: tests/test_sales_reports_new.py
# NG-HEADER: Descripción: Pruebas de reportes top-products, top-customers y net sales con casos límite.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from services.api import app
import random, string

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _create_product(client, title: str, stock: int, price: float) -> int:
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    r = client.post("/catalog/products", json={
        "title": title,
        "initial_stock": stock,
        "supplier_id": None,
        "supplier_sku": None,
        "sku": f"{title[:5]}-{stock}-{int(price*100)}-{rand}",
        "purchase_price": price,
        "sale_price": price,
    })
    assert r.status_code == 200, r.text
    return r.json().get("product_id") or r.json().get("id")


def _confirm_simple_sale(client, pid: int, qty: int, price: float, customer_name: str) -> int:
    r = client.post("/sales", json={
        "customer": {"name": customer_name},
        "items": [{"product_id": pid, "qty": qty, "unit_price": price}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text
    return sale_id


def test_reports_top_and_net_sales(client):
    # Crear productos y ventas
    p1 = _create_product(client, "RepProd1", 100, 20.0)
    p2 = _create_product(client, "RepProd2", 100, 30.0)

    s1 = _confirm_simple_sale(client, p1, 2, 20.0, "Cliente A")  # total 40
    s2 = _confirm_simple_sale(client, p1, 1, 20.0, "Cliente B")  # total 20
    s3 = _confirm_simple_sale(client, p2, 3, 30.0, "Cliente A")  # total 90

    # Devolución parcial sobre s3 (1 unidad de p2)
    rdet = client.get(f"/sales/{s3}")
    assert rdet.status_code == 200
    line_id = rdet.json()["lines"][0]["id"]
    rret = client.post(f"/sales/{s3}/returns", json={"items": [{"sale_line_id": line_id, "qty": 1}], "reason": "ajuste"})
    assert rret.status_code == 200, rret.text

    # Top productos
    rpt = client.get("/sales/reports/top-products", params={"limit": 5})
    assert rpt.status_code == 200, rpt.text
    data_prod = rpt.json()
    assert data_prod["count"] <= 5
    # Validar que product ids presentes
    pids = {it["product_id"] for it in data_prod["items"]}
    assert p1 in pids and p2 in pids

    # Top clientes
    rcust = client.get("/sales/reports/top-customers", params={"limit": 5})
    assert rcust.status_code == 200, rcust.text
    data_cust = rcust.json()
    assert data_cust["count"] <= 5

    # Net sales (simple verificación bruto >= neto)
    rnet = client.get("/sales/reports/net")
    assert rnet.status_code == 200, rnet.text
    net = rnet.json()
    assert net["bruto"] >= net["neto"]
    # Segunda llamada debe venir cached
    rnet2 = client.get("/sales/reports/net")
    assert rnet2.status_code == 200
    assert rnet2.json().get("cached") is True

