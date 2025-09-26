#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sale_discount_clamp.py
# NG-HEADER: Ubicación: tests/test_sale_discount_clamp.py
# NG-HEADER: Descripción: Verifica clamp de discount_amount al confirmar venta y auditoría asociada.
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


def test_discount_clamp_audit(client):
    pid = _create_product(client, "DiscProd", 10, 25.0)
    # Venta con subtotal 50 y discount_amount exagerado
    r = client.post("/sales", json={
        "items": [{"product_id": pid, "qty": 2, "unit_price": 25}],
        "discount_amount": 9999
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text
    # Recuperar detalle
    rdet = client.get(f"/sales/{sale_id}")
    assert rdet.status_code == 200
    total = rdet.json()["total"]
    assert total == 0.0
    # Timeline debe incluir audit sale_discount_clamped
    rtl = client.get(f"/sales/{sale_id}/timeline")
    assert rtl.status_code == 200
    events = rtl.json()["events"]
    assert any(e["type"] == "sale_discount_clamped" for e in events), events

