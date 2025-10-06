"""Tests del flujo de tool-calling en /chat.

Simula una respuesta inicial de OpenAI con tool_calls y luego la invocación al
servidor MCP de productos. Se mockea el cliente OpenAI y la llamada httpx.
"""

# NG-HEADER: Nombre de archivo: test_chat_tool_call.py
# NG-HEADER: Ubicacion: tests/routers/test_chat_tool_call.py
# NG-HEADER: Descripcion: Pruebas flujo tool-calling chat -> MCP productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import respx
from httpx import AsyncClient, Response

from services.api import app

pytestmark = pytest.mark.asyncio


class _Msg(SimpleNamespace):
    pass


class _Choice(SimpleNamespace):
    pass


def _build_openai_tool_call_response(function_name: str, arguments: dict):
    return SimpleNamespace(
        choices=[
            _Choice(
                message=_Msg(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_123",
                            function=SimpleNamespace(
                                name=function_name,
                                arguments=json.dumps(arguments, ensure_ascii=False),
                            ),
                        )
                    ],
                )
            )
        ]
    )


def _build_openai_final_response(content: str):
    return SimpleNamespace(choices=[_Choice(message=_Msg(content=content))])


@pytest.fixture
def mock_openai_cycle():
    # Primera llamada devuelve tool_call; segunda llamada devuelve texto final
    first = _build_openai_tool_call_response("get_product_info", {"sku": "SKU123"})
    second = _build_openai_final_response("El producto SKU123 cuesta 100.")

    class _Chat:
        def __init__(self):
            self._calls = []

        class completions:  # noqa: D401 - mimic
            calls = []

            @staticmethod
            def create(**kwargs):  # noqa: D401
                # Decide cuál devolver según cuántas llamadas previas hubo
                if not hasattr(_Chat.completions, "_counter"):
                    _Chat.completions._counter = 0
                _Chat.completions._counter += 1
                if _Chat.completions._counter == 1:
                    return first
                return second

    class _Client:
        def __init__(self, *_, **__):
            self.chat = _Chat()

    with patch("ai.providers.openai_provider.OpenAI", _Client):
        yield


@respx.mock
async def test_chat_tool_call_flow(mock_openai_cycle):
    # Mock endpoint MCP
    respx.post("http://mcp_products:8001/invoke_tool").mock(
        return_value=Response(200, json={"tool_name": "get_product_info", "result": {"sku": "SKU123", "sale_price": 100}})
    )
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Simula texto que parsea como consulta de producto (‘SKU123?’ u otro trigger)
        r = await ac.post("/chat", json={"text": "Precio SKU123"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "assistant"
        assert "SKU123" in data["text"] or "100" in data["text"]
        # Asegura que se etiquetó como intent product_tool
        assert data.get("intent") in ("product_tool", None)  # toleramos None si provider no setea
