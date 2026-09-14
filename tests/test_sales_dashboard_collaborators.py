#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_dashboard_collaborators.py
# NG-HEADER: Ubicación: tests/test_sales_dashboard_collaborators.py
# NG-HEADER: Descripción: Pruebas automatizadas para el dashboard analítico de compras de colaboradores y clientes
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


def _create_product_with_cost(client, title: str, stock: int, sale_price: float, purchase_price: float, supplier_id: int) -> int:
    rand = _random_str("", 4)
    sku = f"DASH-{rand}"
    payload = {
        "title": title,
        "initial_stock": stock,
        "sku": sku,
        "sale_price": sale_price,
        "purchase_price": purchase_price,
        "supplier_id": supplier_id,
        "supplier_sku": f"SUP-{sku}",
    }
    r = client.post("/catalog/products", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    return data.get("product_id") or data.get("id")


def test_sales_dashboard_collaborators_and_customers(client):
    supplier_id = _create_supplier(client, _random_str("Prov_"))

    # Crear producto con precio de costo 1500 y venta minorista 3000
    prod_id = _create_product_with_cost(client, _random_str("ProdDash_"), 50, sale_price=3000.0, purchase_price=1500.0, supplier_id=supplier_id)

    # 1. Crear cliente Colaborador
    collab_name = _random_str("Collab_")
    r = client.post("/customers", json={
        "name": collab_name,
        "email": f"{collab_name.lower()}@growen.test",
        "kind": "colaborador",
    })
    assert r.status_code == 200, r.text
    collab_id = r.json()["id"]

    # 2. Crear cliente Comercial regular (Minorista)
    cust_name = _random_str("Cliente_")
    r = client.post("/customers", json={
        "name": cust_name,
        "email": f"{cust_name.lower()}@growen.test",
        "kind": "minorista",
    })
    assert r.status_code == 200, r.text
    cust_id = r.json()["id"]

    # 3. Registrar venta a Colaborador (debe liquidar a costo 1500 * 2 = 3000)
    collab_sale_key = _random_str("KEY_COL_")
    r_collab_sale = client.post("/sales", json={
        "customer": {"id": collab_id},
        "customer_id": collab_id,
        "is_collaborator": True,
        "sale_kind": "MOSTRADOR",
        "items": [
            {"product_id": prod_id, "qty": 2, "unit_price": 0.0}
        ]
    }, headers={"Idempotency-Key": collab_sale_key})
    assert r_collab_sale.status_code == 200, r_collab_sale.text
    collab_sale_id = r_collab_sale.json()["sale_id"]

    # Confirmar venta a colaborador
    r_conf = client.post(f"/sales/{collab_sale_id}/confirm")
    assert r_conf.status_code == 200, r_conf.text

    # 4. Registrar venta a Cliente Comercial (a precio regular 3000 * 3 = 9000)
    cust_sale_key = _random_str("KEY_CUST_")
    r_cust_sale = client.post("/sales", json={
        "customer": {"id": cust_id},
        "customer_id": cust_id,
        "is_collaborator": False,
        "sale_kind": "MOSTRADOR",
        "items": [
            {"product_id": prod_id, "qty": 3, "unit_price": 3000.0}
        ]
    }, headers={"Idempotency-Key": cust_sale_key})
    assert r_cust_sale.status_code == 200, r_cust_sale.text
    cust_sale_id = r_cust_sale.json()["sale_id"]

    # Confirmar venta a cliente comercial
    r_conf2 = client.post(f"/sales/{cust_sale_id}/confirm")
    assert r_conf2.status_code == 200, r_conf2.text

    # 5. Consultar Dashboard GET /sales/dashboard/purchases-summary
    r_dash = client.get("/sales/dashboard/purchases-summary")
    assert r_dash.status_code == 200, r_dash.text
    dash_data = r_dash.json()

    summary = dash_data["summary"]
    assert "collaborators" in summary
    assert "customers" in summary
    assert "totals" in summary
    assert "share" in summary

    # Verificación de Colaboradores
    collab_metrics = summary["collaborators"]
    assert collab_metrics["sales_count"] >= 1
    assert collab_metrics["units_count"] >= 2
    assert collab_metrics["total_amount"] >= 3000.0
    assert collab_metrics["unique_buyers"] >= 1

    # Verificación de Clientes
    cust_metrics = summary["customers"]
    assert cust_metrics["sales_count"] >= 1
    assert cust_metrics["units_count"] >= 3
    assert cust_metrics["total_amount"] >= 9000.0
    assert cust_metrics["unique_buyers"] >= 1

    # Verificación de Share
    share = summary["share"]
    assert "collaborators_amount_pct" in share
    assert "collaborators_units_pct" in share

    # Verificación de rankings
    collab_buyers = [b["customer_id"] for b in dash_data["collaborators"]["top_buyers"]]
    assert collab_id in collab_buyers

    cust_buyers = [b["customer_id"] for b in dash_data["customers"]["top_buyers"]]
    assert cust_id in cust_buyers

    # 6. Probar filtros en GET /sales
    # Filtrar solo colaboradores
    r_list_collab = client.get("/sales?is_collaborator=true")
    assert r_list_collab.status_code == 200, r_list_collab.text
    items_collab = r_list_collab.json()["items"]
    assert any(it["id"] == collab_sale_id for it in items_collab)
    for it in items_collab:
        assert it["is_collaborator"] is True
        assert it["customer_kind"] == "colaborador"

    # Filtrar solo clientes (no colaboradores)
    r_list_cust = client.get("/sales?is_collaborator=false")
    assert r_list_cust.status_code == 200, r_list_cust.text
    items_cust = r_list_cust.json()["items"]
    assert any(it["id"] == cust_sale_id for it in items_cust)
    assert not any(it["id"] == collab_sale_id for it in items_cust)
    for it in items_cust:
        assert it["is_collaborator"] is False
