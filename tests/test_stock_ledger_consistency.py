#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_stock_ledger_consistency.py
# NG-HEADER: Ubicación: tests/test_stock_ledger_consistency.py
# NG-HEADER: Descripción: Verifica consistencia stock_ledger vs products.stock tras venta y devolución
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


def test_stock_ledger_sequence_sale_then_return(client):
    pid = _create_product(client, "LedProd", 10, 15.0)
    # Crear venta (qty 4) y confirmar
    r = client.post("/sales", json={
        "customer": {"name": "Led Cust"},
        "items": [{"product_id": pid, "qty": 4, "unit_price": 15}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text

    # Historial tras confirm: debe existir movimiento negativo -4 con balance_after 6
    rh1 = client.get(f"/products/{pid}/stock/history")
    assert rh1.status_code == 200, rh1.text
    items1 = rh1.json()["items"]
    assert any(it["delta"] == -4 and it["balance_after"] == 6 for it in items1), items1

    # Crear devolución parcial (1 unidad)
    rdet = client.get(f"/sales/{sale_id}")
    line_id = rdet.json()["lines"][0]["id"]
    rret = client.post(f"/sales/{sale_id}/returns", json={"items": [{"sale_line_id": line_id, "qty": 1}], "reason": "ajuste"})
    assert rret.status_code == 200, rret.text

    # Historial nuevo: movimiento +1 con balance_after 7 y el producto debe reflejar stock 7 (implícito en último balance)
    rh2 = client.get(f"/products/{pid}/stock/history")
    assert rh2.status_code == 200
    items2 = rh2.json()["items"]
    assert any(it["delta"] == 1 and it["balance_after"] == 7 for it in items2), items2
    # El último (más reciente) balance_after debería ser 7 (orden descendente por created_at/id)
    if items2:
        latest = items2[0]
        assert latest["balance_after"] == 7
