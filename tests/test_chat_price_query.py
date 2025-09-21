# NG-HEADER: Nombre de archivo: test_chat_price_query.py
# NG-HEADER: Ubicación: tests/test_chat_price_query.py
# NG-HEADER: Descripción: Pruebas del intent de precio en el chatbot
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import uuid
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import SessionData, current_session, require_csrf  # noqa: E402

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _create_supplier(slug: str, name: str) -> int:
    resp = client.post("/suppliers", json={"slug": slug, "name": name})
    assert resp.status_code in (200, 201)
    data = resp.json()
    if isinstance(data, dict) and "id" in data:
        return data["id"]
    # listado fallback
    suppliers = client.get("/suppliers").json()
    return suppliers[-1]["id"]


def _create_product(title: str, supplier_id: int, sku: str, sale_price: float) -> dict:
    unique_sku = f"{sku}-{uuid.uuid4().hex[:4]}"
    payload = {
        "title": title,
        "initial_stock": 0,
        "supplier_id": supplier_id,
        "supplier_sku": unique_sku,
        "sku": unique_sku,
        "purchase_price": sale_price,
        "sale_price": sale_price,
    }
    resp = client.post("/catalog/products", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    data["unique_sku"] = payload["sku"]
    return data


def test_chat_returns_price_from_supplier_item():
    sup_id = _create_supplier("sup-chat", "Proveedor Chat")
    prod = _create_product("Fertilizante Premium", sup_id, "FERT-001", 150.0)

    message = {"text": "Cual es el precio del Fertilizante Premium?"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "price_answer"
    assert data.get("data", {}).get("status") in {"ok", "ambiguous"}
    entries = data.get("data", {}).get("entries", [])
    assert entries, data
    entry = entries[0]
    assert abs(entry.get("price") - 150.0) < 0.01
    assert entry.get("currency") == "ARS"
    assert entry.get("sku") in {prod["unique_sku"], "FERT-001"}
    assert "Fertilizante Premium" in data["text"]


def test_chat_requests_clarification_when_multiple_matches():
    sup_id = _create_supplier("sup-chat-clarify", "Proveedor Clarificacion")
    _create_product("Kit Grow Clasico", sup_id, "KIT-CL-001", 120.0)
    _create_product("Kit Grow Deluxe", sup_id, "KIT-CL-002", 150.0)

    message = {"text": "Necesito el precio del Kit Grow"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "price_answer"
    payload = data.get("data", {})
    assert payload.get("status") == "ambiguous"
    assert payload.get("needs_clarification") is True
    assert len(payload.get("entries", [])) >= 2
    text = data["text"].lower()
    assert "encontre varias opciones" in text
    assert "decime cual" in text


def test_chat_informs_when_price_missing():
    sup_id = _create_supplier("sup-chat-np", "Proveedor sin precio")
    prod = _create_product("Podadora Gamma", sup_id, "POD-123", 210.0)

    # Limpiar precio de venta para forzar respuesta de falta de precio
    resp = client.post(f"/products-ex/diagnostics/supplier-item/{prod['supplier_item_id']}/clear-sale")
    assert resp.status_code == 200

    message = {"text": "Precio de la Podadora Gamma"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "price_answer"
    assert data.get("data", {}).get("status") == "missing_price"
    assert "no tiene precio de venta" in data["text"].lower()


def test_chat_handles_unknown_product():
    message = {"text": "Precio de producto inexistente XYZ"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "price_answer"
    assert data.get("data", {}).get("status") in {"no_match", "missing_price"}
    assert "no encontre" in data["text"].lower()
