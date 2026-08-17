#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_http_ollama.py
# NG-HEADER: Ubicación: tests/test_chat_http_ollama.py
# NG-HEADER: Descripción: Contrato HTTP determinista y sanitizado con Ollama local.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from types import SimpleNamespace
import uuid

import pytest

from ai.intent_classifier import UserIntent


@pytest.mark.asyncio
async def test_http_ollama_uses_catalog_and_sanitizes_public_payload(client, monkeypatch):
    async def price_intent(*_args, **_kwargs):
        return UserIntent.CONSULTA_PRECIO

    monkeypatch.setattr("services.routers.chat.classify_intent", price_intent)
    monkeypatch.setattr(
        "services.routers.chat.AIRouter.get_provider",
        lambda *_args, **_kwargs: SimpleNamespace(name="ollama"),
    )

    supplier = await client.post(
        "/suppliers",
        json={"slug": f"http-chat-{uuid.uuid4().hex[:8]}", "name": "Proveedor HTTP"},
    )
    assert supplier.status_code in {200, 201}
    supplier_id = supplier.json()["id"]
    sku = f"MAC-{uuid.uuid4().hex[:6]}"
    product = await client.post(
        "/catalog/products",
        json={
            "title": "Maceta HTTP Controlada",
            "initial_stock": 6,
            "supplier_id": supplier_id,
            "supplier_sku": sku,
            "sku": sku,
            "purchase_price": 450,
            "sale_price": 450,
        },
    )
    assert product.status_code == 200

    public_response = await client.post(
        "/chat",
        headers={"X-User-Roles": "guest"},
        json={"text": "Precio de Maceta HTTP Controlada"},
    )
    assert public_response.status_code == 200
    public_data = public_response.json()
    entry = public_data["data"]["results"][0]
    assert public_data["type"] == "product_answer"
    assert entry["price"] == 450
    assert entry["stock_status"] == "ok"
    assert "sku" not in entry
    assert "stock_qty" not in entry
    assert "supplier_name" not in entry
    assert "disponibilidad" in public_data["text"].lower()

    staff_response = await client.post(
        "/chat",
        headers={"X-User-Roles": "colaborador"},
        json={"text": "Precio de Maceta HTTP Controlada"},
    )
    assert staff_response.status_code == 200
    staff_entry = staff_response.json()["data"]["results"][0]
    assert staff_entry["stock_qty"] == 6
    assert staff_entry["sku"] == sku
    assert staff_entry["supplier_name"] == "Proveedor HTTP"
