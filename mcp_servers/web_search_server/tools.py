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
from mcp_servers.security import require_mcp_auth
from agent_core.chat_policy import allowed_roles_for
from agent_core.tool_security import contains_sensitive_material, sanitize_text

# Roles permitidos (puedes afinar en futuro)
_DEFAULT_HOSTS = {"duckduckgo.com", "html.duckduckgo.com", "lite.duckduckgo.com"}


def _allowed_search_base(value: str) -> bool:
    parsed = _url.urlparse(value)
    configured = {
        host.strip().lower()
        for host in os.getenv("WEB_SEARCH_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.hostname.lower() in (_DEFAULT_HOSTS | configured)
    )


def _ddg_unwrap(href: str) -> str:
    """Normaliza enlaces de DuckDuckGo que usan redirección /l/?uddg=..."""
    try:
        if href.startswith("/l/?"):
            q = _url.urlparse(href).query
            params = _url.parse_qs(q)
            uddg = params.get("uddg", [None])[0]
            if uddg:
                return _url.unquote(uddg)
    except (TypeError, ValueError):
        return href
    return href


@require_mcp_auth(allowed_roles=allowed_roles_for("search_web"))
async def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Busca resultados web (DuckDuckGo HTML) y devuelve títulos/URLs/snippets.

    Nota: es un MVP. En producción se recomienda una API dedicada (Bing/Serper/etc.).
    """
    if not query or not isinstance(query, str):
        raise ValueError("query requerido")
    query = sanitize_text(query, max_chars=256)
    if contains_sensitive_material(query):
        raise ValueError("query contiene material potencialmente sensible")
    max_results = max(1, min(int(max_results), 10))
    try:
        # Probar múltiples variantes HTML de DuckDuckGo para mayor resiliencia
        bases: List[str] = []
        env_base = os.getenv("WEB_SEARCH_BASE")
        if env_base and _allowed_search_base(env_base):
            bases.append(env_base)
        # Defaults conocidos (orden de preferencia)
        bases.extend([
            "https://duckduckgo.com/html/",
            "https://html.duckduckgo.com/html/",
            "https://lite.duckduckgo.com/lite/",
        ])

        params = {"q": query}
        items: List[Dict[str, Any]] = []
        timed_out = False
        headers = {"User-Agent": os.getenv("WEB_SEARCH_UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers=headers,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            for base in bases:
                try:
                    resp = await client.get(base, params=params)
                    if resp.status_code != 200:
                        continue
                    if len(resp.content) > int(os.getenv("WEB_SEARCH_MAX_RESPONSE_BYTES", "1000000")):
                        continue
                    if "text/html" not in resp.headers.get("content-type", "").lower():
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
                        parsed_href = _url.urlparse(href)
                        if parsed_href.scheme not in {"http", "https"}:
                            continue
                        tmp.append({
                            "title": sanitize_text(title, max_chars=300),
                            "url": href[:2_000],
                            "snippet": sanitize_text(snippet or "", max_chars=800) or None,
                        })
                        if len(tmp) >= max_results:
                            break
                    if tmp:
                        items = tmp
                        break
                except httpx.TimeoutException:
                    timed_out = True
                    continue
                except httpx.RequestError:
                    # Intentar siguiente base
                    continue
        result = {
            "items": items,
            "query": query,
            "source": "duckduckgo" if items else "duckduckgo:none",
        }
        if not items and timed_out:
            result["error"] = "timeout"
        elif not items:
            result["error"] = "upstream_failure"
        return result
    except Exception:
        return {"items": [], "query": query, "error": "network_failure"}


TOOLS_REGISTRY = {
    "search_web": search_web,
}


async def invoke_tool(tool_name: str, parameters: Dict[str, Any], token: str) -> Dict[str, Any]:
    if tool_name not in TOOLS_REGISTRY:
        raise KeyError(f"Tool desconocida: {tool_name}")
    if not isinstance(parameters, dict):
        raise ValueError("parameters debe ser dict")
    if tool_name == "search_web":
        q = parameters.get("query")
        k = parameters.get("max_results", 5)
        return await search_web(token, query=str(q), max_results=int(k))
    raise KeyError(f"Tool no implementada: {tool_name}")
