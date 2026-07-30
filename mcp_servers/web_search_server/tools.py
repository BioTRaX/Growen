#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: tools.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/tools.py
# NG-HEADER: Descripción: Tools MCP para búsqueda web básica (MVP).
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Any, Dict, List
import asyncio
import hashlib
import ipaddress
import socket
from io import BytesIO
import os
import urllib.parse as _url
import httpx
from bs4 import BeautifulSoup  # type: ignore
from pypdf import PdfReader
from mcp_servers.security import require_mcp_auth
from agent_core.chat_policy import allowed_roles_for
from agent_core.tool_security import contains_sensitive_material, sanitize_text

# Roles permitidos (puedes afinar en futuro)
_DEFAULT_HOSTS = {"duckduckgo.com", "html.duckduckgo.com", "lite.duckduckgo.com"}
_ALLOWED_FETCH_MIME = {"text/html", "application/pdf"}


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
        parsed = _url.urlparse(href)
        is_redirect = (
            href.startswith("/l/?")
            or (
                parsed.hostname in _DEFAULT_HOSTS
                and parsed.path.rstrip("/") == "/l"
            )
        )
        if is_redirect:
            q = parsed.query
            params = _url.parse_qs(q)
            uddg = params.get("uddg", [None])[0]
            if uddg:
                return _url.unquote(uddg)
    except (TypeError, ValueError):
        return href
    return href


def _is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_global


async def _resolve_public_host(hostname: str, port: int = 443) -> set[str]:
    if not hostname:
        raise ValueError("La URL no contiene host")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = {str(literal)}
    else:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        addresses = {record[4][0] for record in records}
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise ValueError("El destino resuelve a una red no pública")
    return addresses


def _validate_fetch_url(value: str) -> _url.ParseResult:
    parsed = _url.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Sólo se permiten URLs HTTPS públicas")
    if parsed.username or parsed.password:
        raise ValueError("No se permiten credenciales embebidas en la URL")
    if parsed.port not in {None, 443}:
        raise ValueError("Sólo se permite el puerto HTTPS estándar")
    return parsed


def _extract_peer_ip(response: httpx.Response) -> str | None:
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None
    try:
        peer = stream.get_extra_info("server_addr")
    except Exception:
        return None
    if isinstance(peer, (tuple, list)) and peer:
        return str(peer[0])
    return str(peer) if peer else None


def _clean_html(content: bytes, max_chars: int) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "noscript", "iframe", "object", "embed"]):
        node.decompose()
    return sanitize_text(soup.get_text(" ", strip=True), max_chars=max_chars)


def _extract_pdf(content: bytes, max_chars: int) -> str:
    reader = PdfReader(BytesIO(content))
    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        remaining = max_chars - total
        if remaining <= 0:
            break
        chunks.append(text[:remaining])
        total += len(chunks[-1])
    return sanitize_text("\n".join(chunks), max_chars=max_chars)


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


@require_mcp_auth(allowed_roles=allowed_roles_for("search_web"))
async def fetch_web_document(url: str) -> Dict[str, Any]:
    """Lee HTML o PDF público con límites estrictos y defensas SSRF."""
    if os.getenv("WEB_FETCH_ENABLED", "1") != "1":
        raise ValueError("La lectura web está deshabilitada")
    current_url = sanitize_text(str(url), max_chars=2_000)
    max_redirects = min(max(int(os.getenv("WEB_FETCH_MAX_REDIRECTS", "3")), 0), 3)
    timeout = float(os.getenv("WEB_FETCH_TIMEOUT_SECONDS", "12"))
    max_text_chars = int(os.getenv("WEB_FETCH_MAX_TEXT_CHARS", "50000"))
    allowed_mime = {
        item.strip().lower()
        for item in os.getenv(
            "WEB_FETCH_ALLOWED_MIME", "text/html,application/pdf"
        ).split(",")
        if item.strip()
    } & _ALLOWED_FETCH_MIME
    redirects: list[str] = []
    headers = {"User-Agent": os.getenv("WEB_SEARCH_UA", "Growen-WebFetch/2.0")}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
        headers=headers,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        for redirect_count in range(max_redirects + 1):
            parsed = _validate_fetch_url(current_url)
            resolved = await _resolve_public_host(parsed.hostname or "")
            async with client.stream("GET", current_url) as response:
                peer_ip = _extract_peer_ip(response)
                if peer_ip and (not _is_public_ip(peer_ip) or peer_ip not in resolved):
                    raise ValueError("El destino conectado no coincide con el DNS público validado")
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirect_count >= max_redirects:
                        raise ValueError("Se excedió el máximo de redirects")
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect sin destino")
                    next_url = _url.urljoin(current_url, location)
                    _validate_fetch_url(next_url)
                    redirects.append(next_url)
                    current_url = next_url
                    continue
                response.raise_for_status()
                mime_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if mime_type not in allowed_mime:
                    raise ValueError(f"MIME no permitido: {mime_type or 'desconocido'}")
                max_bytes = int(
                    os.getenv(
                        "WEB_FETCH_MAX_PDF_BYTES" if mime_type == "application/pdf" else "WEB_FETCH_MAX_HTML_BYTES",
                        "10000000" if mime_type == "application/pdf" else "2000000",
                    )
                )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("El documento supera el tamaño permitido")
                    chunks.append(chunk)
                content = b"".join(chunks)
                text = (
                    _extract_pdf(content, max_text_chars)
                    if mime_type == "application/pdf"
                    else _clean_html(content, max_text_chars)
                )
                return {
                    "url": str(response.url),
                    "mime_type": mime_type,
                    "text": text,
                    "content_hash": hashlib.sha256(content).hexdigest(),
                    "bytes": size,
                    "redirects": redirects,
                }
    raise ValueError("No fue posible leer el documento")


TOOLS_REGISTRY = {
    "search_web": search_web,
    "fetch_web_document": fetch_web_document,
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
    if tool_name == "fetch_web_document":
        return await fetch_web_document(token, url=str(parameters.get("url") or ""))
    raise KeyError(f"Tool no implementada: {tool_name}")
