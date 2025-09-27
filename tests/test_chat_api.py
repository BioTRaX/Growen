# NG-HEADER: Nombre de archivo: test_chat_api.py
# NG-HEADER: Ubicacion: tests/test_chat_api.py
# NG-HEADER: Descripcion: Pruebas de integracion para el endpoint /chat con intent de productos
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
    suppliers = client.get("/suppliers").json()
    return suppliers[-1]["id"]


def _create_product(title: str, supplier_id: int, sku: str, sale_price: float, stock: int) -> dict:
    unique_sku = f"{sku}-{uuid.uuid4().hex[:4]}"
    payload = {
        "title": title,
        "initial_stock": stock,
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


def test_chat_returns_product_payload_with_stock():
    sup_id = _create_supplier("sup-chat", "Proveedor Chat")
    prod = _create_product("Fertilizante Premium", sup_id, "FERT-001", 150.0, stock=7)

    message = {"text": "Cual es el precio del Fertilizante Premium?"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "product_answer"
    assert data["intent"] == "price"
    payload = data.get("data", {})
    results = payload.get("results", [])
    assert results, payload
    entry = results[0]
    assert abs(entry.get("price") - 150.0) < 0.01
    assert entry.get("stock_qty") == 7
    assert entry.get("stock_status") == "ok"
    text = data["text"].lower()
    assert "en stock" in text


def test_chat_requests_clarification_when_multiple_matches():
    sup_id = _create_supplier("sup-chat-clarify", "Proveedor Clarificacion")
    _create_product("Kit Grow Clasico", sup_id, "KIT-CL-001", 120.0, stock=3)
    _create_product("Kit Grow Deluxe", sup_id, "KIT-CL-002", 150.0, stock=8)

    message = {"text": "Necesito el precio del Kit Grow"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "product_answer"
    payload = data.get("data", {})
    assert payload.get("status") == "ambiguous"
    assert payload.get("intent") == data["intent"]
    assert payload.get("needs_clarification") is True or len(payload.get("results", [])) > 1
    text = data["text"].lower()
    assert "tambien encontre" in text or "tambien encontre" in text


def test_chat_informs_when_price_missing():
    sup_id = _create_supplier("sup-chat-np", "Proveedor sin precio")
    prod = _create_product("Podadora Gamma", sup_id, "POD-123", 210.0, stock=2)

    resp = client.post(f"/products-ex/diagnostics/supplier-item/{prod['supplier_item_id']}/clear-sale")
    assert resp.status_code == 200

    message = {"text": "Precio de la Podadora Gamma"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "product_answer"
    payload = data.get("data", {})
    assert payload.get("status") in {"ok", "ambiguous"}
    assert payload.get("results", [])
    text = data["text"].lower()
    assert "sin precio" in text


def test_chat_handles_unknown_product():
    message = {"text": "Precio de producto inexistente XYZ"}
    resp = client.post("/chat", json=message)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "product_answer"
    payload = data.get("data", {})
    assert payload.get("status") == "no_match"
    assert payload.get("results") == []
    assert "no encontre" in data["text"].lower() or "no encontre" in data["text"].lower()

def test_chat_followup_clarification_flow():
    sup_id = _create_supplier("sup-chat-follow", "Proveedor Follow")
    _create_product("Sustrato Grow Mix", sup_id, "SUS-001", 80.0, stock=4)
    _create_product("Sustrato Grow Mix Premium", sup_id, "SUS-002", 95.0, stock=1)
    _create_product("Sustrato Coco Mix", sup_id, "SUS-003", 70.0, stock=0)

    resp = client.post("/chat", json={"text": "Necesito el precio del sustrato"})
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["type"] == "product_answer"

    resp_follow = client.post("/chat", json={"text": "Sustratos"})
    assert resp_follow.status_code == 200
    follow_data = resp_follow.json()
    assert follow_data["type"] == "clarify_prompt"
    assert "sustrato" in follow_data["text"].lower()

    resp_confirm = client.post("/chat", json={"text": "si"})
    assert resp_confirm.status_code == 200
    confirm_data = resp_confirm.json()
    assert confirm_data["type"] == "product_answer"
    payload = confirm_data.get("data", {})
    assert payload.get("results")

def test_chat_hides_metrics_for_cliente():
    sup_id = _create_supplier("sup-chat-client", "Proveedor Cliente")
    _create_product("Tester Cliente", sup_id, "TC-001", 50.0, stock=2)

    original_override = app.dependency_overrides[current_session]
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "cliente")
    try:
        resp = client.post("/chat", json={"text": "Precio tester cliente"})
        assert resp.status_code == 200, resp.text
        payload = resp.json().get("data", {})
        assert payload.get("metrics") is None
    finally:
        app.dependency_overrides[current_session] = original_override
