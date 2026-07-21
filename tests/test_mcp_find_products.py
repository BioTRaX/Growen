#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_mcp_find_products.py
# NG-HEADER: Ubicación: tests/test_mcp_find_products.py
# NG-HEADER: Descripción: Pruebas de tool find_products_by_name y flujo búsqueda->info
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from ai.providers.openai_provider import OpenAIProvider
from agent_core.mcp_client import mcp_client_manager

pytestmark = pytest.mark.asyncio


async def test_call_mcp_tool_network_error(monkeypatch):
    provider = OpenAIProvider()

    async def fail_call(**kwargs):
        return {"error": "tool_network_failure"}

    monkeypatch.setattr(mcp_client_manager, "call_tool", fail_call)
    out = await provider.call_mcp_tool(
        tool_name="get_product_info",
        parameters={"sku": "ABC"},
        user_role="viewer",
    )
    assert isinstance(out, dict) and out.get("error") == "tool_network_failure"


async def test_find_products_by_name_tool_direct(monkeypatch):
    # Probamos la tool directamente usando el servidor MCP simulado
    from mcp_servers.products_server import tools as t
    async def fake_get(url, *a, **k):
        class R:
            status_code = 200
            def json(self_inner):
                return [
                    {"id": 1, "name": "Sustrato Growmix 50L", "sku": "GRO_0050_MIX", "tags": ["#Sustrato"]},
                    {"id": 2, "name": "Sustrato Growmix 25L", "sku": "GRO_0025_MIX"},
                ]
            def raise_for_status(self_inner):
                return None
        return R()
    class DummyClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
        async def get(self, url, headers=None, **kwargs):
            return await fake_get(url)
    monkeypatch.setattr("httpx.AsyncClient", DummyClient)
    res = await t.find_products_by_name.__wrapped__(query="sustrato growmix")
    assert res["count"] == 2
    assert any(item["sku"] == "GRO_0050_MIX" for item in res["items"])
    assert res["items"][0]["tags"] == ["#Sustrato"]
    assert res["items"][1]["tags"] == []
