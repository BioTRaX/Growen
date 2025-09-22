# NG-HEADER: Nombre de archivo: test_purchase_validation.py
# NG-HEADER: Ubicación: tests/test_purchase_validation.py
# NG-HEADER: Descripción: Pruebas del endpoint de validación de compras respecto a SKUs de proveedor
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

_NEXT = 1


def setup_supplier_with_product():
    global _NEXT
    n = _NEXT
    _NEXT += 1
    # Crear proveedor
    supplier_slug = f"spv-{n}"
    r = client.post("/suppliers", json={"slug": supplier_slug, "name": f"Santa Planta Valid {n}"})
    assert r.status_code in (200, 201)
    sid = (r.json() or {}).get("id") or client.get("/suppliers").json()[-1]["id"]
    # Crear SupplierProduct directo (sin producto interno) para el SKU
    supplier_sku = f"SKU-EXISTE-{n}-{uuid.uuid4().hex[:6]}"
    r = client.post(
        f"/suppliers/{sid}/items",
        json={
            "supplier_product_id": supplier_sku,
            "title": f"Item {n}",
            "product_id": None,
        },
    )
    assert r.status_code in (200, 201), r.text
    sp_id = (r.json() or {}).get("id")
    return sid, sp_id, supplier_sku


def create_purchase_with_lines(supplier_id: int, existing_sku: str):
    # Crear compra
    remito = f"R-VAL-{uuid.uuid4().hex[:8]}"
    r = client.post("/purchases", json={"supplier_id": supplier_id, "remito_number": remito, "remito_date": "2025-09-01"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # Agregar líneas: una con SKU existente, otra con SKU inexistente
    payload = {
        "lines": [
            {"supplier_sku": existing_sku, "title": "OK", "qty": 1, "unit_cost": 10, "op": "upsert"},
            {"supplier_sku": "SKU-NO-EXISTE", "title": "X", "qty": 1, "unit_cost": 10, "op": "upsert"},
        ]
    }
    r = client.put(f"/purchases/{pid}", json=payload)
    assert r.status_code == 200
    return pid


def test_validate_marks_missing_skus_as_unmatched():
    sid, _, supplier_sku = setup_supplier_with_product()
    pid = create_purchase_with_lines(sid, supplier_sku)
    r = client.post(f"/purchases/{pid}/validate")
    assert r.status_code == 200
    data = r.json()
    assert data["lines"] == 2
    assert data["unmatched"] == 1
    assert "SKU-NO-EXISTE" in (data.get("missing_skus") or [])


def test_validate_ok_when_sku_exists():
    sid, _, supplier_sku = setup_supplier_with_product()
    # Compra con sola línea existente
    remito = f"R-VAL-{uuid.uuid4().hex[:8]}"
    r = client.post("/purchases", json={"supplier_id": sid, "remito_number": remito, "remito_date": "2025-09-02"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.put(f"/purchases/{pid}", json={"lines": [{"supplier_sku": supplier_sku, "title": "OK", "qty": 1, "unit_cost": 10, "op": "upsert"}]})
    assert r.status_code == 200
    r = client.post(f"/purchases/{pid}/validate")
    assert r.status_code == 200
    data = r.json()
    assert data["lines"] == 1
    assert data["unmatched"] == 0


def test_validate_mixed_cases():
    sid, _, supplier_sku = setup_supplier_with_product()
    remito = f"R-VAL-{uuid.uuid4().hex[:8]}"
    r = client.post("/purchases", json={"supplier_id": sid, "remito_number": remito, "remito_date": "2025-09-03"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # Tres líneas: 2 existentes y 1 inexistente
    lines = [
        {"supplier_sku": supplier_sku, "title": "A", "qty": 1, "unit_cost": 10, "op": "upsert"},
        {"supplier_sku": "SKU-NO-EXISTE", "title": "B", "qty": 1, "unit_cost": 10, "op": "upsert"},
        {"supplier_sku": supplier_sku, "title": "C", "qty": 2, "unit_cost": 15, "op": "upsert"},
    ]
    r = client.put(f"/purchases/{pid}", json={"lines": lines})
    assert r.status_code == 200
    r = client.post(f"/purchases/{pid}/validate")
    assert r.status_code == 200
    data = r.json()
    assert data["lines"] == 3
    assert data["unmatched"] == 1
