#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_payments_report.py
# NG-HEADER: Ubicación: tests/test_sales_payments_report.py
# NG-HEADER: Descripción: Pruebas del endpoint /reports/sales/payments con filtros y agregados
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from services.api import app
import random, string, datetime as dt

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


def _confirm_sale_with_payment(client, pid: int, amount: float, method: str, qty: int = 1):
    r = client.post("/sales", json={
        "customer": {"name": f"Cliente {method}"},
        "items": [{"product_id": pid, "qty": qty, "unit_price": amount/qty}],
        "payments": [{"method": method, "amount": amount}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text
    return sale_id


def test_payments_report_basic_filters(client):
    pid = _create_product(client, "PayRpt", 50, 10.0)
    _confirm_sale_with_payment(client, pid, 30.0, "efectivo")
    _confirm_sale_with_payment(client, pid, 45.0, "tarjeta")
    _confirm_sale_with_payment(client, pid, 25.0, "transferencia")

    # Reporte general
    r = client.get("/reports/sales/payments")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] >= 3
    total_sum = sum(it["amount"] for it in data["items"])
    assert abs(total_sum - data["total_amount"]) < 0.01
    assert len(data["by_method"]) >= 2

    # Filtro por método
    r_m = client.get("/reports/sales/payments", params={"method": "tarjeta"})
    assert r_m.status_code == 200
    data_m = r_m.json()
    assert all(it["method"] == "tarjeta" for it in data_m["items"])

    # Filtros de fecha (usar hoy como from_date)
    today = dt.datetime.utcnow().date().strftime("%Y-%m-%d")
    r_f = client.get("/reports/sales/payments", params={"from_date": today})
    assert r_f.status_code == 200
    data_f = r_f.json()
    assert data_f["count"] >= 1

    # Formato fecha inválido
    r_bad = client.get("/reports/sales/payments", params={"from_date": "2025/99/99"})
    assert r_bad.status_code == 400
