# NG-HEADER: Nombre de archivo: test_chat_ws_price.py
# NG-HEADER: Ubicación: tests/test_chat_ws_price.py
# NG-HEADER: Descripción: Pruebas asíncronas de precio WebSocket con servidor ASGI real.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import json
import uuid

import pytest
from websockets.asyncio.client import connect


async def _create_supplier(client, slug: str, name: str) -> int:
    response = await client.post("/suppliers", json={"slug": slug, "name": name})
    assert response.status_code in (200, 201)
    data = response.json()
    if isinstance(data, dict) and "id" in data:
        return data["id"]
    return (await client.get("/suppliers")).json()[-1]["id"]


async def _create_product(client, title: str, supplier_id: int, sku: str, sale_price: float, stock: int) -> dict:
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
    response = await client.post("/catalog/products", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    data["unique_sku"] = unique_sku
    return data


async def _receive_non_ping(ws) -> dict:
    message = json.loads(await ws.recv())
    while message.get("role") == "ping":
        message = json.loads(await ws.recv())
    return message


@pytest.mark.asyncio
async def test_ws_returns_product_answer_and_copy(client, live_asgi_server):
    supplier_id = await _create_supplier(client, "sup-ws", "Proveedor WS")
    product = await _create_product(client, "Medidor PH Digital", supplier_id, "MPH-001", 999.99, 4)

    async with connect(f"{live_asgi_server['ws']}/ws") as ws:
        await ws.send("Precio del Medidor PH Digital")
        message = await _receive_non_ping(ws)
    assert message.get("role") == "assistant"
    assert message.get("type") == "product_answer"
    assert message.get("intent") in ("product_tool", "price")
    results = message.get("data", {}).get("results", [])
    assert results
    entry = results[0]
    assert abs(entry.get("price") - 999.99) < 0.01
    assert entry.get("stock_status") == "ok"
    assert "stock_qty" not in entry
    assert "sku" not in entry
    assert "variant_skus" not in entry
    assert "supplier_name" not in entry
    assert entry.get("stock_status") == "ok"
    assert "disponibilidad" in (message.get("text") or "").lower()

    second = await _create_product(client, "Tijera Pro", supplier_id, "TJ-001", 120.0, 1)
    response = await client.post(f"/products-ex/diagnostics/supplier-item/{second['supplier_item_id']}/clear-sale")
    assert response.status_code == 200
    async with connect(f"{live_asgi_server['ws']}/ws") as ws:
        await ws.send("Precio de la Tijera Pro")
        message = await _receive_non_ping(ws)
    assert message.get("type") == "product_answer"
    assert "no tiene precio" in (message.get("text") or "").lower()
    assert message.get("data", {}).get("results")


@pytest.mark.asyncio
async def test_ws_handles_unknown_product(live_asgi_server):
    async with connect(f"{live_asgi_server['ws']}/ws") as ws:
        await ws.send("Precio de producto inexistente XYZ")
        message = await _receive_non_ping(ws)
    assert message.get("role") == "assistant"
    assert message.get("type") == "product_answer"
    assert message.get("data", {}).get("status") == "no_match"
    assert message.get("data", {}).get("results") == []
    assert "no encontr" in (message.get("text") or "").lower()
