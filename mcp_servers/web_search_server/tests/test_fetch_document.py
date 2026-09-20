#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_fetch_document.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/tests/test_fetch_document.py
# NG-HEADER: Descripción: Pruebas focales de extracción y defensas SSRF de fetch_web_document.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest

from mcp_servers.web_search_server.tools import (
    _clean_html,
    _ddg_unwrap,
    _resolve_public_host,
    _validate_fetch_url,
)


def test_ddg_unwrap_accepts_scheme_relative_redirect():
    href = (
        "//duckduckgo.com/l/?uddg="
        "https%3A%2F%2Fexample.com%2Fmanual.pdf&rut=opaque"
    )
    assert _ddg_unwrap(href) == "https://example.com/manual.pdf"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/manual",
        "https://user:secret@example.com/manual",
        "https://example.com:8443/manual",
        "file:///etc/passwd",
    ],
)
def test_fetch_rejects_non_public_url_shapes(url: str):
    with pytest.raises(ValueError):
        _validate_fetch_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.1", "169.254.1.2", "::1"])
async def test_fetch_rejects_private_literal_ips(host: str):
    with pytest.raises(ValueError, match="no pública"):
        await _resolve_public_host(host)


def test_html_extraction_removes_executable_content():
    text = _clean_html(
        b"<html><body><h1>Manual oficial</h1><script>alert('x')</script><p>Dosis 2 ml.</p></body></html>",
        1000,
    )
    assert "Manual oficial" in text
    assert "Dosis 2 ml." in text
    assert "alert" not in text
