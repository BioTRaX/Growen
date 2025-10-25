#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/tools.py
# NG-HEADER: Descripción: Tools MCP para búsqueda web básica (MVP).
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Any, Dict
import os
import httpx
from bs4 import BeautifulSoup  # type: ignore

# Roles permitidos (puedes afinar en futuro)
_ALLOWED_ROLES = {"admin", "colaborador"}


async def search_web(query: str, user_role: str, max_results: int = 5) -> Dict[str, Any]:
    """Busca resultados web (DuckDuckGo HTML) y devuelve títulos/URLs/snippets.

    Nota: es un MVP. En producción se recomienda una API dedicada (Bing/Serper/etc.).
    """
    if user_role not in _ALLOWED_ROLES:
        raise PermissionError("rol insuficiente")
    if not query or not isinstance(query, str):
        raise ValueError("query requerido")
    try:
        base = os.getenv("WEB_SEARCH_BASE", "https://duckduckgo.com/html/")
        params = {"q": query}
        items = []
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(base, params=params)
            if resp.status_code != 200:
                return {"items": [], "source": "duckduckgo", "status": resp.status_code}
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a.result__a"):
                title = a.get_text(" ").strip()
                href = a.get("href")
                if not href:
                    continue
                # snippet opcional
                parent = a.find_parent("div", class_="result__body")
                snippet = None
                if parent:
                    sn_div = parent.select_one(".result__snippet")
                    snippet = sn_div.get_text(" ").strip() if sn_div else None
                items.append({"title": title, "url": href, "snippet": snippet})
                if len(items) >= max_results:
                    break
        return {"items": items, "query": query, "source": "duckduckgo"}
    except Exception:
        return {"items": [], "query": query, "error": "network_failure"}


TOOLS_REGISTRY = {
    "search_web": search_web,
}


async def invoke_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name not in TOOLS_REGISTRY:
        raise KeyError(f"Tool desconocida: {tool_name}")
    if not isinstance(parameters, dict):
        raise ValueError("parameters debe ser dict")
    user_role = parameters.get("user_role")
    if not user_role or not isinstance(user_role, str):
        raise ValueError("user_role requerido")
    if tool_name == "search_web":
        q = parameters.get("query")
        k = parameters.get("max_results", 5)
        return await search_web(query=str(q), user_role=user_role, max_results=int(k))
    raise KeyError(f"Tool no implementada: {tool_name}")
