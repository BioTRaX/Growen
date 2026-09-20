#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_mcp_client.py
# NG-HEADER: Ubicación: tests/test_mcp_client.py
# NG-HEADER: Descripción: Pruebas del catálogo y filtrado del cliente MCP.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
import httpx

from agent_core.mcp_client import (
    DiscoveredTool,
    MCPClientManager,
    MCPServerConfig,
)


def test_role_policy_hides_privileged_tools():
    manager = MCPClientManager()
    assert manager._allowed("get_product_info", "guest") is True
    assert manager._allowed("get_product_full_info", "guest") is False
    assert manager._allowed("get_product_full_info", "admin") is True
    assert manager._allowed("search_web", "colaborador") is True
    assert manager._allowed("new_unreviewed_tool", "admin") is False


@pytest.mark.asyncio
async def test_openai_schema_is_derived_from_discovery(monkeypatch):
    manager = MCPClientManager()
    discovered = [
        DiscoveredTool(
            name="get_product_info",
            description="Consulta un producto",
            input_schema={"type": "object", "properties": {"sku": {"type": "string"}}},
            server_name="products",
        )
    ]

    async def fake_list_tools(role: str):
        assert role == "admin"
        return discovered

    monkeypatch.setattr(manager, "list_tools", fake_list_tools)
    schemas = await manager.openai_tools("admin")
    assert schemas[0]["function"]["name"] == "get_product_info"
    assert schemas[0]["function"]["parameters"] == discovered[0].input_schema


@pytest.mark.asyncio
async def test_transport_normalizes_streamable_http_trailing_slash(monkeypatch):
    manager = MCPClientManager()
    captured: dict[str, str] = {}
    sentinel = object()

    def fake_transport(url: str, *, http_client):
        captured["url"] = url
        assert http_client is not None
        return sentinel

    monkeypatch.setattr("agent_core.mcp_client.streamable_http_client", fake_transport)
    monkeypatch.setattr(manager, "_token", lambda *_args, **_kwargs: "test-token")
    client, transport = await manager._open_session(
        MCPServerConfig("web_search", "http://mcp-web/mcp", "audience"),
        "admin",
    )
    await client.aclose()
    assert transport is sentinel
    assert captured["url"] == "http://mcp-web/mcp/"


@pytest.mark.asyncio
async def test_explicit_server_avoids_discovering_unrelated_mcp(monkeypatch):
    manager = MCPClientManager()
    discovered_servers: list[str] = []

    async def fail_global_discovery(*_args, **_kwargs):
        raise AssertionError("No debe descubrir todos los servidores")

    async def targeted_discovery(config, *_args, **_kwargs):
        discovered_servers.append(config.name)
        manager._tool_servers["search_web"] = config.name
        return []

    class FailingTransport:
        async def __aenter__(self):
            raise httpx.TimeoutException("smoke")

        async def __aexit__(self, *_args):
            return False

    async def fake_open_session(config, *_args, **_kwargs):
        assert config.name == "web_search"
        return httpx.AsyncClient(), FailingTransport()

    monkeypatch.setattr(manager, "list_tools", fail_global_discovery)
    monkeypatch.setattr(manager, "_list_server_tools", targeted_discovery)
    monkeypatch.setattr(manager, "_open_session", fake_open_session)

    result = await manager.call_tool(
        "search_web",
        {"query": "growen"},
        role="admin",
        server_name="web_search",
    )
    assert result == {"error": "tool_timeout"}
    assert discovered_servers == ["web_search"]
