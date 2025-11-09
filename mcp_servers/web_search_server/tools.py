#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/tools.py
# NG-HEADER: Descripción: Tools MCP para búsqueda web básica (MVP).
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Any, Dict, List
import os
import urllib.parse as _url
import httpx
from bs4 import BeautifulSoup  # type: ignore

# Roles permitidos (puedes afinar en futuro)
_ALLOWED_ROLES = {"admin", "colaborador"}


def _ddg_unwrap(href: str) -> str:
    """Normaliza enlaces de DuckDuckGo que usan redirección /l/?uddg=..."""
    try:
        if href.startswith("/l/?"):
            q = _url.urlparse(href).query
            params = _url.parse_qs(q)
            uddg = params.get("uddg", [None])[0]
            if uddg:
                return _url.unquote(uddg)
    except Exception:
        pass
    return href


async def search_web(query: str, user_role: str, max_results: int = 5) -> Dict[str, Any]:
    """Busca resultados web (DuckDuckGo HTML) y devuelve títulos/URLs/snippets.

    Nota: es un MVP. En producción se recomienda una API dedicada (Bing/Serper/etc.).
    """
    if user_role not in _ALLOWED_ROLES:
        raise PermissionError("rol insuficiente")
    if not query or not isinstance(query, str):
        raise ValueError("query requerido")
    try:
        # Probar múltiples variantes HTML de DuckDuckGo para mayor resiliencia
        bases: List[str] = []
        env_base = os.getenv("WEB_SEARCH_BASE")
        if env_base:
            bases.append(env_base)
        # Defaults conocidos (orden de preferencia)
        bases.extend([
            "https://duckduckgo.com/html/",
            "https://html.duckduckgo.com/html/",
            "https://lite.duckduckgo.com/lite/",
        ])

        params = {"q": query}
        items: List[Dict[str, Any]] = []
        headers = {"User-Agent": os.getenv("WEB_SEARCH_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")}
        async with httpx.AsyncClient(timeout=8.0, headers=headers, trust_env=True) as client:
            for base in bases:
                try:
                    resp = await client.get(base, params=params)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Selectores alternativos según versión html/lite
                    anchors = soup.select("a.result__a")
                    if not anchors:
                        anchors = soup.select("a.result-link, a.result__url")
                    tmp: List[Dict[str, Any]] = []
                    for a in anchors:
                        title = a.get_text(" ").strip()
                        href = a.get("href") or ""
                        if not title or not href:
                            continue
                        href = _ddg_unwrap(href)
                        # snippet opcional
                        parent = a.find_parent("div")
                        snippet = None
                        if parent:
                            sn_div = parent.select_one(".result__snippet, .result-snippet")
                            if sn_div:
                                snippet = sn_div.get_text(" ").strip()
                        tmp.append({"title": title, "url": href, "snippet": snippet})
                        if len(tmp) >= max_results:
                            break
                    if tmp:
                        items = tmp
                        break
                except Exception:
                    # Intentar siguiente base
                    continue
        return {"items": items, "query": query, "source": "duckduckgo" if items else "duckduckgo:none"}
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
