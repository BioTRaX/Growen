#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_lifecycle.py
# NG-HEADER: Ubicación: tests/test_sales_lifecycle.py
# NG-HEADER: Descripción: Test funcional del ciclo de vida de ventas con devolución parcial
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest, random, string
from fastapi.testclient import TestClient
from services.api import app


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
    return r.json()["product_id"] if "product_id" in r.json() else r.json().get("id")


def test_full_lifecycle_with_return(client):
    # Crear producto base
    pid = _create_product(client, "ProdTest", 20, 100.0)

    # Crear venta BORRADOR sin líneas (posteriormente agregamos)
    r = client.post("/sales", json={"customer": {"name": "Juan"}, "items": []})
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]

    # Agregar líneas
    r = client.post(f"/sales/{sale_id}/lines", json={"ops": [
        {"op": "add", "product_id": pid, "qty": 5, "unit_price": 100}
    ]})
    assert r.status_code == 200, r.text
    total = r.json()["total"]
    assert total == 500.0

    # Confirmar (afecta stock)
    r = client.post(f"/sales/{sale_id}/confirm")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONFIRMADA"

    # Entregar
    r = client.post(f"/sales/{sale_id}/deliver")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ENTREGADA"

    # Devolver parcialmente 2 unidades
    r_det = client.get(f"/sales/{sale_id}")
    assert r_det.status_code == 200
    line_id = r_det.json()["lines"][0]["id"]
    r_ret = client.post(f"/sales/{sale_id}/returns", json={"items": [{"sale_line_id": line_id, "qty": 2}], "reason": "Cliente no lo quiso"})
    assert r_ret.status_code == 200, r_ret.text
    assert r_ret.json()["lines"] == 1

    # Listar devoluciones
    r_list = client.get(f"/sales/{sale_id}/returns")
    assert r_list.status_code == 200
    data = r_list.json()
    assert data["total"] == 1
    assert data["items"][0]["lines"][0]["qty"] == 2.0

    # Anular venta (debe fallar porque ya ENTREGADA pero permitimos anular ENTREGADA; stock se repone restante)
    r_annul = client.post(f"/sales/{sale_id}/annul", params={"reason": "Error"})
    assert r_annul.status_code == 200, r_annul.text
    assert r_annul.json()["status"] == "ANULADA"
