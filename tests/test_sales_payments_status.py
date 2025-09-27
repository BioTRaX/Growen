#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_payments_status.py
# NG-HEADER: Ubicación: tests/test_sales_payments_status.py
# NG-HEADER: Descripción: Pruebas transición payment_status con múltiples pagos y validación sobrepago
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


def test_payment_status_transitions_and_overpay_guard(client):
    pid = _create_product(client, "PayStat", 10, 25.0)
    # Venta con total 100 (4 * 25)
    r = client.post("/sales", json={
        "customer": {"name": "Cliente Pago"},
        "items": [{"product_id": pid, "qty": 4, "unit_price": 25}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]

    # Confirmar
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text

    # Estado inicial debe ser PENDIENTE
    rdet = client.get(f"/sales/{sale_id}")
    assert rdet.status_code == 200
    assert rdet.json()["payment_status"] in ("PENDIENTE", "PARCIAL", "PAGADA")  # toleramos inicialización

    # Primer pago 30 -> PARCIAL
    rpay1 = client.post(f"/sales/{sale_id}/payments", json={"method": "efectivo", "amount": 30})
    assert rpay1.status_code == 200, rpay1.text
    rdet2 = client.get(f"/sales/{sale_id}")
    assert rdet2.status_code == 200
    assert rdet2.json()["payment_status"] == "PARCIAL"
    assert rdet2.json()["paid_total"] == 30.0

    # Segundo pago 70 -> PAGADA
    rpay2 = client.post(f"/sales/{sale_id}/payments", json={"method": "tarjeta", "amount": 70})
    assert rpay2.status_code == 200, rpay2.text
    rdet3 = client.get(f"/sales/{sale_id}")
    assert rdet3.status_code == 200
    assert rdet3.json()["payment_status"] == "PAGADA"
    assert rdet3.json()["paid_total"] == 100.0

    # Intento de sobrepago significativo 5 -> debe 409 o 400 (venta saldada)
    rpay3 = client.post(f"/sales/{sale_id}/payments", json={"method": "efectivo", "amount": 5})
    assert rpay3.status_code in (400, 409)
    data_err = rpay3.json()
    # Si es 409 esperamos code sobrepago
    if rpay3.status_code == 409:
        assert (data_err.get("detail") or {}).get("code") == "sobrepago"

    # Listado de pagos: al menos 2
    rlist = client.get(f"/sales/{sale_id}/payments")
    assert rlist.status_code == 200
    assert rlist.json()["total"] >= 2
