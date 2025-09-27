#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_new_endpoints.py
# NG-HEADER: Ubicación: tests/test_sales_new_endpoints.py
# NG-HEADER: Descripción: Pruebas de endpoints nuevos: timeline, payments list, stock history, quick customer search y clamp descuento.
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
    response = None
    for _ in range(16):
        rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        prefix = (title[:3].upper() + 'XXX')[:3]
        serial = random.randint(1000, 9999)
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        canonical_sku = f"{prefix}_{serial}_{suffix}"
        response = client.post("/catalog/products", json={
            "title": title,
            "initial_stock": stock,
            "supplier_id": None,
            "supplier_sku": None,
            "sku": canonical_sku,
            "purchase_price": price,
            "sale_price": price,
            "slug": f"{title.lower()}-{rand.lower()}",
            "category_name": f"General {rand}",
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("product_id") or data.get("id")
        if response.status_code != 409:
            break
    assert response is not None and response.status_code == 200, response.text if response else 'no response'
    data = response.json()
    return data.get("product_id") or data.get("id")


def test_timeline_and_payments_listing(client):
    pid = _create_product(client, "TLProd", 50, 10.0)
    # Crear venta con una línea y un pago inicial
    r = client.post("/sales", json={
        "customer": {"name": "Cliente TL"},
        "items": [{"product_id": pid, "qty": 3, "unit_price": 10}],
        "payments": [{"method": "efectivo", "amount": 10}],
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]

    # Confirmar
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text

    # Agregar otro pago
    rpay = client.post(f"/sales/{sale_id}/payments", json={"method": "tarjeta", "amount": 5})
    assert rpay.status_code == 200, rpay.text

    # Timeline
    rtl = client.get(f"/sales/{sale_id}/timeline")
    assert rtl.status_code == 200, rtl.text
    events = rtl.json()["events"]
    assert any(e["type"].startswith("sale_create") or e["type"] == "sale_create" for e in events)
    assert any(e["type"] == "sale_confirm" for e in events)
    assert any(e["type"] == "payment" for e in events)
    # Orden cronológico (ascendente por at)
    timestamps = [e["at"] for e in events]
    assert timestamps == sorted(timestamps)

    # Endpoint de pagos dedicado
    rpl = client.get(f"/sales/{sale_id}/payments")
    assert rpl.status_code == 200
    data = rpl.json()
    assert data["sale_id"] == sale_id
    assert data["total"] >= 2  # al menos los dos pagos


def test_stock_history_and_quick_search_and_clamp(client):
    # Crear cliente y producto
    pid = _create_product(client, "ClampProd", 30, 50.0)
    # Venta con descuento_amount exagerado para forzar clamp
    r = client.post("/sales", json={
        "customer": {"name": "Cliente Clamp", "document_number": "30111222"},
        "items": [{"product_id": pid, "qty": 2, "unit_price": 50}],
        "discount_amount": 1000  # excede subtotal (100)
    })
    assert r.status_code == 200, r.text
    sale_id = r.json()["sale_id"]

    # Confirmar (debe generar audit de clamp y ajustar total a 0)
    rc = client.post(f"/sales/{sale_id}/confirm")
    assert rc.status_code == 200, rc.text

    # Ver detalle para confirmar total no negativo
    rdet = client.get(f"/sales/{sale_id}")
    assert rdet.status_code == 200
    total = rdet.json()["total"]
    assert total == 0.0 or total >= 0.0

    # Historial stock del producto (debe existir un movimiento negativo por la venta confirmada)
    rh = client.get(f"/products/{pid}/stock/history")
    assert rh.status_code == 200, rh.text
    hist = rh.json()["items"]
    assert any(it["delta"] < 0 for it in hist)

    # Búsqueda rápida de cliente
    rs = client.get("/customers/search", params={"q": "Clamp"})
    assert rs.status_code == 200, rs.text
    results = rs.json()["items"]
    assert any("Clamp" in (c["name"] or "") for c in results)


