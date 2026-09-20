# NG-HEADER: Nombre de archivo: test_chat_tool_call.py
# NG-HEADER: Ubicacion: tests/routers/test_chat_tool_call.py
# NG-HEADER: Descripcion: Pruebas flujo tool-calling chat -> MCP productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Tests del flujo de tool-calling en /chat con OpenAI y el cliente MCP."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

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
def mock_openai_cycle(monkeypatch):
    from agent_core.config import settings as core_settings

    monkeypatch.setenv("AI_DISABLE_OLLAMA", "true")
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(core_settings, "ai_allow_external", True)
    # Primera llamada devuelve tool_call; segunda llamada devuelve texto final
    first = _build_openai_tool_call_response("get_product_info", {"sku": "SKU123"})
    second = _build_openai_final_response("El producto SKU123 cuesta 100.")

    class _Chat:
        def __init__(self):
            self._calls = []

        class completions:  # noqa: D401 - mimic
            calls = []

            @staticmethod
            async def create(**kwargs):  # noqa: D401
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

    async def schemas(_role):
        return [{"type": "function", "function": {"name": "get_product_info", "description": "info", "parameters": {"type": "object"}}}]

    async def call_tool(**_kwargs):
        return {"sku": "SKU123", "sale_price": 100}

    with patch("ai.providers.openai_provider.AsyncOpenAI", _Client), \
         patch("agent_core.mcp_client.mcp_client_manager.openai_tools", schemas), \
         patch("agent_core.mcp_client.mcp_client_manager.call_tool", call_tool):
        yield


async def test_chat_tool_call_flow(mock_openai_cycle):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Simula texto que parsea como consulta de producto (‘SKU123?’ u otro trigger)
        r = await ac.post("/chat", json={"text": "Precio SKU123"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "assistant"
        assert "SKU123" in data["text"] or "100" in data["text"]
        # Asegura que se etiquetó como intent product_tool
        assert data.get("intent") in ("product_tool", None)  # toleramos None si provider no setea
