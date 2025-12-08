#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_mcp_find_products.py
# NG-HEADER: Ubicación: tests/test_mcp_find_products.py
# NG-HEADER: Descripción: Pruebas de tool find_products_by_name y flujo búsqueda->info
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest
import json
from ai.providers.openai_provider import OpenAIProvider

pytestmark = pytest.mark.asyncio


class DummyResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or json.dumps(self._json)

    def json(self):
        return self._json


async def test_call_mcp_tool_network_error(monkeypatch):
    provider = OpenAIProvider()
    # Simular error de red levantando httpx.RequestError en post
    class DummyClient:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            return False
        async def post(self, *a, **k):
            import httpx
            raise httpx.RequestError("dns fail")
    monkeypatch.setenv("MCP_PRODUCTS_URL", "http://no-resolve:9999/invoke_tool")
    monkeypatch.setattr("httpx.AsyncClient", DummyClient)
    out = await provider.call_mcp_tool(tool_name="get_product_info", parameters={"sku": "ABC", "user_role": "viewer"})
    assert isinstance(out, dict) and out.get("error") == "tool_network_failure"


async def test_find_products_by_name_tool_direct(monkeypatch):
    # Probamos la tool directamente usando el servidor MCP simulado
    from mcp_servers.products_server import tools as t
    async def fake_get(url, *a, **k):
        class R:
            status_code = 200
            def json(self_inner):
                return [
                    {"name": "Sustrato Growmix 50L", "sku": "GROWMIX50"},
                    {"name": "Sustrato Growmix 25L", "sku": "GROWMIX25"},
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
    res = await t.find_products_by_name(query="sustrato growmix", user_role="viewer")
    assert res["count"] == 2
    assert any(item["sku"] == "GROWMIX50" for item in res["items"])  # sanity
