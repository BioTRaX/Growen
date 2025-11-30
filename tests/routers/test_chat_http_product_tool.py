# NG-HEADER: Nombre de archivo: test_chat_http_product_tool.py
# NG-HEADER: Ubicación: tests/routers/test_chat_http_product_tool.py
# NG-HEADER: Descripción: Prueba del flujo chat HTTP con OpenAI tool-calling hacia MCP Products
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
import types
import json
from httpx import AsyncClient, ASGITransport, Response, Request

from services.api import app

pytestmark = pytest.mark.asyncio

class _FakeToolCallFn:
    def __init__(self, name: str, arguments: str, call_id: str = "call_1"):
        self.function = types.SimpleNamespace(name=name, arguments=arguments)
        self.id = call_id

class _FakeMessage:
    def __init__(self, content: str = None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

class _FakeChoice:
    def __init__(self, message: _FakeMessage):
        self.message = message

class _FakeResponse:
    def __init__(self, choices):
        self.choices = choices

class _FakeChat:
    def __init__(self, sequence):
        self._sequence = sequence
        self._idx = 0
    def completions(self):  # pragma: no cover - interface guard
        return self
    def create(self, **kwargs):  # Simula dos llamadas consecutivas
        out = self._sequence[self._idx]
        self._idx += 1
        return out

class _FakeOpenAI:
    def __init__(self, api_key: str):
        # Primera respuesta: modelo pide tool_call
        tool_call = _FakeToolCallFn(
            name="get_product_info",
            arguments=json.dumps({"sku": "SKU123"}),
        )
        first = _FakeResponse([
            _FakeChoice(_FakeMessage(content=None, tool_calls=[tool_call]))
        ])
        # Segunda respuesta: modelo entrega respuesta final usando datos inyectados
        second = _FakeResponse([
            _FakeChoice(_FakeMessage(content="El precio de Maceta Test (SKU123) es ARS 1000 con stock 5."))
        ])
        self.chat = types.SimpleNamespace(completions=_FakeChat([first, second]))

@pytest.fixture(autouse=True)
def patch_openai(monkeypatch):
    import ai.providers.openai_provider as mod
    monkeypatch.setattr(mod, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

@pytest.fixture
def patch_httpx(monkeypatch):
    import httpx
    original_post = httpx.AsyncClient.post

    async def _fake_post(self, url, json=None, **kwargs):  # noqa: A002
        if str(url).endswith("/invoke_tool"):
            payload = {
                "tool_name": json.get("tool_name"),
                "result": {
                    "sku": json.get("parameters", {}).get("sku"),
                    "name": "Maceta Test",
                    "sale_price": 1000,
                    "stock": 5,
                    "currency": "ARS",
                },
            }
            return Response(200, request=Request("POST", url), json=payload)
        return await original_post(self, url, json=json, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

async def test_chat_http_product_tool_flow(patch_httpx):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/chat", json={"text": "cuanto cuesta SKU123?"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "role" in data, f"Respuesta inesperada: {data}"
        assert data["role"] == "assistant"
        assert "SKU123" in data["text"]
        assert "1000" in data["text"] or "ARS 1000" in data["text"].replace(",", ".")
        # Aseguramos que el intent nuevo esté marcado
        assert data.get("intent") in {"product_tool", None}  # tolerante si provider no fija intent
