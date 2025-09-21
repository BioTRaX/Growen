# NG-HEADER: Nombre de archivo: test_prices_defaults.py
# NG-HEADER: Ubicación: tests/routers/test_prices_defaults.py
# NG-HEADER: Descripción: Pruebas de defaults de precios (venta=compra) y backfill
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import uuid
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def create_supplier(slug: str, name: str) -> int:
    r = client.post("/suppliers", json={"slug": slug, "name": name})
    assert r.status_code in (200, 201)
    # tomar el último id creado
    rows = client.get("/suppliers").json()
    return rows[-1]["id"]


def test_minimal_create_sets_sale_equals_buy():
    sup = create_supplier("sup_min", "Sup Min")
    # crear producto mínimo con purchase_price pero sin sale_price
    uniq = uuid.uuid4().hex[:6]
    sku = f"SKU-X-{uniq}"
    r = client.post(
        "/catalog/products",
        json={
            "title": "Prod X",
            "initial_stock": 0,
            "supplier_id": sup,
            "supplier_sku": sku,
            "sku": sku,
            "purchase_price": 123.45,
        },
    )
    assert r.status_code == 200
    sp_id = r.json()["supplier_item_id"]
    diag = client.get(f"/products-ex/diagnostics/supplier-item/{sp_id}").json()
    assert diag["current_purchase_price"] == 123.45
    assert diag["current_sale_price"] == 123.45


def test_confirm_applies_sale_when_missing():
    sup = create_supplier("sup_conf", "Sup Conf")
    # crear compra con una línea que resuelve por SKU
    r = client.post("/purchases", json={"supplier_id": sup, "remito_number": "R-100", "remito_date": "2025-01-01"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # crear producto con precios iniciales iguales (luego forzaremos missing sale)
    uniq = uuid.uuid4().hex[:6]
    sku = f"SKU-Y-{uniq}"
    r = client.post(
        "/catalog/products",
        json={
            "title": "Prod Y",
            "initial_stock": 0,
            "supplier_id": sup,
            "supplier_sku": sku,
            "sku": sku,
            "purchase_price": 50.00,
            "sale_price": 50.00,
        },
    )
    assert r.status_code == 200
    sp_id = r.json()["supplier_item_id"]
    # forzamos a que la línea tenga el sku y precio efectivo distinto para validar update
    client.put(
        f"/purchases/{pid}",
        json={
            "lines": [
                {
                    "supplier_sku": sku,
                    "title": "Prod Y",
                    "qty": 2,
                    "unit_cost": 80.0,
                    "line_discount": 25.0,
                }
            ]
        },
    )
    client.post(f"/purchases/{pid}/validate")
    # forzar falta de precio de venta antes de confirmar
    client.post(f"/products-ex/diagnostics/supplier-item/{sp_id}/clear-sale")
    client.post(f"/purchases/{pid}/confirm")
    # precio efectivo esperado: 80 * (1 - 0.25) = 60.0
    diag = client.get(f"/products-ex/diagnostics/supplier-item/{sp_id}").json()
    assert diag["current_purchase_price"] == 60.0
    # venta se repone con el valor efectivo de compra
    assert diag["current_sale_price"] == 60.0


def test_fill_missing_sale_backfill():
    sup = create_supplier("sup_bf", "Sup BF")
    # crear producto con sólo compra y limpiar venta para simular faltante
    uniq = uuid.uuid4().hex[:6]
    sku = f"SKU-Z-{uniq}"
    r = client.post(
        "/catalog/products",
        json={
            "title": "Prod Z",
            "initial_stock": 0,
            "supplier_id": sup,
            "supplier_sku": sku,
            "sku": sku,
            "purchase_price": 10.0,
            "sale_price": 10.0,
        },
    )
    sp_id = r.json()["supplier_item_id"]
    # forzar falta de venta y ejecutar backfill
    client.post(f"/products-ex/diagnostics/supplier-item/{sp_id}/clear-sale")
    client.post("/products-ex/supplier-items/fill-missing-sale", json={"supplier_id": sup})
    diag = client.get(f"/products-ex/diagnostics/supplier-item/{sp_id}").json()
    assert diag["current_sale_price"] == 10.0
