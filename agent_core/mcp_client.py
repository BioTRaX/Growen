#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: mcp_client.py
# NG-HEADER: Ubicación: agent_core/mcp_client.py
# NG-HEADER: Descripción: Descubre e invoca herramientas MCP reales para Growen.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent_core.config import settings
from agent_core.detect_mcp_url import get_mcp_products_url, get_mcp_web_search_url
from agent_core.tool_security import sanitize_tool_result
from services.auth import create_mcp_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    audience: str
    enabled: bool = True


@dataclass(frozen=True)
class DiscoveredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


TOOL_ROLES: dict[str, set[str]] = {
    "find_products_by_name": {"guest", "cliente", "proveedor", "colaborador", "admin"},
    "get_product_info": {"guest", "cliente", "proveedor", "colaborador", "admin"},
    "get_product_full_info": {"admin", "colaborador"},
    "search_web": {"admin", "colaborador"},
}


class MCPClientManager:
    """Mantiene un catálogo MCP con cache y autorización por rol."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str, str], tuple[float, list[DiscoveredTool]]] = {}
        self._tool_servers: dict[str, str] = {}

    def server_configs(self) -> list[MCPServerConfig]:
        return [
            MCPServerConfig("products", get_mcp_products_url(), settings.mcp_products_audience),
            MCPServerConfig("web_search", get_mcp_web_search_url(), settings.mcp_web_search_audience),
        ]

    @staticmethod
    def _allowed(tool_name: str, role: str) -> bool:
        allowed_roles = TOOL_ROLES.get(tool_name, set())
        return role in allowed_roles

    @staticmethod
    def _token(role: str, audience: str) -> str:
        return create_mcp_token(sub="growen-agent", role=role, audience=audience)

    @staticmethod
    def _normalize_exception(exc: Exception) -> dict[str, str]:
        message = str(exc).lower()
        if "401" in message or "token" in message:
            return {"error": "tool_unauthorized"}
        if "403" in message or "autoriz" in message:
            return {"error": "tool_forbidden"}
        if "429" in message or "rate" in message or "límite" in message:
            return {"error": "tool_rate_limited"}
        return {"error": "tool_network_failure"}

    async def _open_session(self, config: MCPServerConfig, role: str):
        token = self._token(role, config.audience)
        client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(8.0),
            follow_redirects=False,
        )
        transport = streamable_http_client(config.url, http_client=client)
        return client, transport

    async def _list_server_tools(self, config: MCPServerConfig, role: str) -> list[DiscoveredTool]:
        cache_key = (config.name, config.url, role, settings.mcp_protocol_version)
        cached = self._cache.get(cache_key)
        ttl = max(0, settings.mcp_tool_catalog_ttl_seconds)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1]

        http_client, transport = await self._open_session(config, role)
        try:
            async with http_client:
                async with transport as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        response = await session.list_tools()
        except Exception as exc:
            self._cache.pop(cache_key, None)
            logger.warning("No se pudo descubrir MCP server=%s error=%s", config.name, type(exc).__name__)
            return []

        tools: list[DiscoveredTool] = []
        for tool in response.tools:
            name = str(tool.name)
            if not self._allowed(name, role):
                continue
            schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {"type": "object"}
            discovered = DiscoveredTool(
                name=name,
                description=str(tool.description or ""),
                input_schema=dict(schema),
                server_name=config.name,
            )
            tools.append(discovered)
            previous = self._tool_servers.get(name)
            if previous and previous != config.name:
                logger.error("Colisión MCP tool=%s servers=%s,%s", name, previous, config.name)
                continue
            self._tool_servers[name] = config.name
        self._cache[cache_key] = (time.monotonic(), tools)
        return tools

    async def list_tools(self, role: str) -> list[DiscoveredTool]:
        tools: list[DiscoveredTool] = []
        for config in self.server_configs():
            if config.enabled:
                tools.extend(await self._list_server_tools(config, role))
        return tools

    async def openai_tools(self, role: str) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in await self.list_tools(role)
        ]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        role: str,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        if not self._allowed(tool_name, role):
            return {"error": "tool_not_allowed"}

        if tool_name not in self._tool_servers:
            await self.list_tools(role)
        target = server_name or self._tool_servers.get(tool_name)
        config = next((item for item in self.server_configs() if item.name == target), None)
        if not config:
            return {"error": "tool_not_found"}

        clean_arguments = {key: value for key, value in arguments.items() if key != "user_role"}
        http_client, transport = await self._open_session(config, role)
        try:
            async with http_client:
                async with transport as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=clean_arguments)
        except httpx.TimeoutException:
            self.invalidate()
            return {"error": "tool_timeout"}
        except Exception as exc:
            self.invalidate()
            logger.warning("Fallo MCP tool=%s error=%s", tool_name, type(exc).__name__)
            return self._normalize_exception(exc)

        if bool(getattr(result, "isError", False) or getattr(result, "is_error", False)):
            combined = " ".join(
                str(getattr(content, "text", "")) for content in getattr(result, "content", [])
            )
            return self._normalize_exception(RuntimeError(combined or "tool failure"))

        structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return sanitize_tool_result(structured, external=config.name == "web_search")

        for content in getattr(result, "content", []):
            text = getattr(content, "text", None)
            if not text:
                continue
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return sanitize_tool_result(decoded, external=config.name == "web_search")
            except json.JSONDecodeError:
                return sanitize_tool_result({"content": text}, external=config.name == "web_search")
        return {"error": "tool_empty_result"}

    def invalidate(self) -> None:
        self._cache.clear()
        self._tool_servers.clear()


mcp_client_manager = MCPClientManager()
