# NG-HEADER: Nombre de archivo: test_chat_ws_price.py
# NG-HEADER: Ubicación: tests/test_chat_ws_price.py
# NG-HEADER: Descripción: Prueba del canal WS para intent de precio con type product_answer y copy consistente
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


def _receive_non_ping(ws):
    msg = ws.receive_json()
    while isinstance(msg, dict) and msg.get("role") == "ping":
        msg = ws.receive_json()
    return msg


def test_ws_returns_product_answer_and_copy():
    sup_id = _create_supplier("sup-ws", "Proveedor WS")
    product = _create_product("Medidor PH Digital", sup_id, "MPH-001", 999.99, stock=4)

    with client.websocket_connect("/ws") as ws:
        ws.send_text("Precio del Medidor PH Digital")
        msg = _receive_non_ping(ws)
        assert msg.get("role") == "assistant"
        assert msg.get("type") == "product_answer"
        assert msg.get("intent") == "price"
        payload = msg.get("data", {})
        results = payload.get("results", [])
        assert results, payload
        entry = results[0]
        assert abs(entry.get("price") - 999.99) < 0.01
        assert entry.get("stock_status") == "ok"
        assert entry.get("stock_qty") == 4
        assert product["unique_sku"] in {entry.get("sku"), entry.get("variant_skus", [None])[0]}
        text = (msg.get("text") or "").lower()
        assert "en stock" in text

    prod2 = _create_product("Tijera Pro", sup_id, "TJ-001", 120.0, stock=1)
    resp = client.post(f"/products-ex/diagnostics/supplier-item/{prod2['supplier_item_id']}/clear-sale")
    assert resp.status_code == 200

    with client.websocket_connect("/ws") as ws2:
        ws2.send_text("Precio de la Tijera Pro")
        msg2 = _receive_non_ping(ws2)
        assert msg2.get("role") == "assistant"
        assert msg2.get("type") == "product_answer"
        text2 = (msg2.get("text") or "").lower()
        assert "sin precio" in text2
        payload2 = msg2.get("data", {})
        assert payload2.get("results")


def test_ws_handles_unknown_product():
    with client.websocket_connect("/ws") as ws:
        ws.send_text("Precio de producto inexistente XYZ")
        msg = _receive_non_ping(ws)
        assert msg.get("role") == "assistant"
        assert msg.get("type") == "product_answer"
        payload = msg.get("data", {})
        assert payload.get("status") == "no_match"
        assert payload.get("results") == []
        assert "no encontré" in (msg.get("text") or "").lower() or "no encontre" in (msg.get("text") or "").lower()
