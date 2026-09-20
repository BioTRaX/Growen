#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_collaborators.py
# NG-HEADER: Ubicación: tests/test_sales_collaborators.py
# NG-HEADER: Descripción: Pruebas para ventas a colaboradores con precio de costo
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import random
import string
import pytest
from fastapi.testclient import TestClient
from services.api import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _random_str(prefix: str = "T", k: int = 5) -> str:
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=k))


def _create_supplier(client, name: str | None = None) -> int:
    sname = name or _random_str("Sup_")
    sslug = sname.lower().replace(" ", "-").replace("_", "-")
    r = client.post("/suppliers", json={"slug": sslug, "name": sname, "contact_name": "Contacto " + sname})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_product_with_cost(client, title: str, stock: int, sale_price: float, purchase_price: float | None = None, supplier_id: int | None = None) -> int:
    rand = _random_str("", 4)
    sku = f"{title[:5]}-{stock}-{rand}"
    payload = {
        "title": title,
        "initial_stock": stock,
        "sku": sku,
        "sale_price": sale_price,
    }
    if purchase_price is not None:
        payload["purchase_price"] = purchase_price
    if supplier_id is not None:
        payload["supplier_id"] = supplier_id
        payload["supplier_sku"] = f"SUP-{sku}"

    r = client.post("/catalog/products", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    return data.get("product_id") or data.get("id")


def test_create_and_filter_collaborator_customer(client):
    name = _random_str("Colaborador_")
    # Crear cliente tipo colaborador
    r = client.post("/customers", json={
        "name": name,
        "email": f"{name.lower()}@growen.test",
        "kind": "colaborador",
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    # Detalle cliente
    r_get = client.get(f"/customers/{cid}")
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["kind"] == "colaborador"

    # Filtrar por tipo
    r_list = client.get("/customers", params={"kind": "colaborador", "q": name})
    assert r_list.status_code == 200, r_list.text
    items = r_list.json()["items"]
    assert any(c["id"] == cid and c["kind"] == "colaborador" for c in items)


def test_catalog_search_returns_cost_price(client):
    sup_id = _create_supplier(client)
    title = _random_str("ProdCostSearch_")
    pid = _create_product_with_cost(client, title, stock=10, sale_price=200.0, purchase_price=120.0, supplier_id=sup_id)

    r = client.get("/sales/catalog/search", params={"q": title})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    matched = next((it for it in items if it["product_id"] == pid), None)
    assert matched is not None
    assert matched["price"] == 200.0
    assert matched["cost_price"] == 120.0


def test_quote_and_create_sale_for_collaborator(client):
    sup_id = _create_supplier(client)
    title = _random_str("ProdCollab_")
    pid = _create_product_with_cost(client, title, stock=20, sale_price=250.0, purchase_price=150.0, supplier_id=sup_id)

    # Crear cliente colaborador
    c_name = _random_str("Empleado_")
    r_cust = client.post("/customers", json={"name": c_name, "kind": "colaborador"})
    assert r_cust.status_code == 200
    collab_cid = r_cust.json()["id"]

    # Crear cliente común
    r_regular = client.post("/customers", json={"name": _random_str("Cliente_"), "kind": "minorista"})
    assert r_regular.status_code == 200
    regular_cid = r_regular.json()["id"]

    # 1. Cotizar para cliente regular (precio de venta = 250.0)
    r_q_reg = client.post("/sales/quote", json={
        "customer_id": regular_cid,
        "items": [{"product_id": pid, "qty": 2}],
    })
    assert r_q_reg.status_code == 200, r_q_reg.text
    assert r_q_reg.json()["total_amount"] == 500.0
    assert r_q_reg.json()["lines"][0]["unit_price"] == 250.0

    # 2. Cotizar para cliente colaborador (precio de costo = 150.0)
    r_q_collab = client.post("/sales/quote", json={
        "customer_id": collab_cid,
        "items": [{"product_id": pid, "qty": 2}],
    })
    assert r_q_collab.status_code == 200, r_q_collab.text
    assert r_q_collab.json()["total_amount"] == 300.0
    assert r_q_collab.json()["lines"][0]["unit_price"] == 150.0

    # 3. Cotizar con flag is_collaborator explícito
    r_q_flag = client.post("/sales/quote", json={
        "is_collaborator": True,
        "items": [{"product_id": pid, "qty": 3}],
    })
    assert r_q_flag.status_code == 200, r_q_flag.text
    assert r_q_flag.json()["total_amount"] == 450.0
    assert r_q_flag.json()["lines"][0]["unit_price"] == 150.0

    # 4. Crear venta para colaborador en BORRADOR
    r_sale = client.post("/sales", json={
        "customer": {"id": collab_cid},
        "items": [{"product_id": pid, "qty": 2}],
    })
    assert r_sale.status_code == 200, r_sale.text
    sale_id = r_sale.json()["sale_id"]

    # Detalle de la venta
    r_det = client.get(f"/sales/{sale_id}")
    assert r_det.status_code == 200, r_det.text
    detail = r_det.json()
    assert detail["total"] == 300.0
    line = detail["lines"][0]
    assert line["unit_price"] == 150.0
    assert line["unit_cost_snapshot"] == 150.0

    # 5. Confirmar venta (afecta stock)
    r_conf = client.post(f"/sales/{sale_id}/confirm")
    assert r_conf.status_code == 200, r_conf.text
    assert r_conf.json()["status"] == "CONFIRMADA"

    # Verificar stock
    r_search = client.get("/sales/catalog/search", params={"q": title})
    matched = next(it for it in r_search.json()["items"] if it["product_id"] == pid)
    assert matched["stock"] == 18.0


def test_quote_fails_when_product_lacks_cost(client):
    # Crear producto sin precio de compra ni proveedor
    title = _random_str("ProdNoCost_")
    pid = _create_product_with_cost(client, title, stock=10, sale_price=100.0, purchase_price=None, supplier_id=None)

    c_name = _random_str("Empleado_")
    r_cust = client.post("/customers", json={"name": c_name, "kind": "colaborador"})
    collab_cid = r_cust.json()["id"]

    # Cotizar debe fallar con 422
    r_quote = client.post("/sales/quote", json={
        "customer_id": collab_cid,
        "items": [{"product_id": pid, "qty": 1}],
    })
    assert r_quote.status_code == 422, r_quote.text
    assert "no tiene precio de costo registrado" in r_quote.json()["detail"]

    # Crear venta debe fallar con 422
    r_sale = client.post("/sales", json={
        "customer": {"id": collab_cid},
        "items": [{"product_id": pid, "qty": 1}],
    })
    assert r_sale.status_code == 422, r_sale.text
    assert "no tiene precio de costo registrado" in r_sale.json()["detail"]


def test_add_line_to_collaborator_sale_uses_cost_price(client):
    sup_id = _create_supplier(client)
    title = _random_str("ProdLineOps_")
    pid = _create_product_with_cost(client, title, stock=10, sale_price=300.0, purchase_price=180.0, supplier_id=sup_id)

    # Crear cliente colaborador
    c_name = _random_str("Empleado_")
    r_cust = client.post("/customers", json={"name": c_name, "kind": "colaborador"})
    collab_cid = r_cust.json()["id"]

    # Crear venta vacía para el colaborador
    r_sale = client.post("/sales", json={"customer": {"id": collab_cid}, "items": []})
    assert r_sale.status_code == 200
    sale_id = r_sale.json()["sale_id"]

    # Agregar línea sin especificar unit_price
    r_lines = client.post(f"/sales/{sale_id}/lines", json={
        "ops": [{"op": "add", "product_id": pid, "qty": 2}]
    })
    assert r_lines.status_code == 200, r_lines.text
    assert r_lines.json()["total"] == 360.0  # 2 * 180.0

    # Comprobar detalle
    r_det = client.get(f"/sales/{sale_id}")
    detail = r_det.json()
    assert detail["lines"][0]["unit_price"] == 180.0
    assert detail["lines"][0]["unit_cost_snapshot"] == 180.0
