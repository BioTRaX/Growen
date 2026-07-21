#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_mcp_client.py
# NG-HEADER: Ubicación: tests/test_mcp_client.py
# NG-HEADER: Descripción: Pruebas del catálogo y filtrado del cliente MCP.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest

from agent_core.mcp_client import DiscoveredTool, MCPClientManager


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
