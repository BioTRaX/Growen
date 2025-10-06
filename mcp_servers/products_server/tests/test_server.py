#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_server.py
# NG-HEADER: Ubicación: mcp_servers/products_server/tests/test_server.py
# NG-HEADER: Descripción: Pruebas unitarias e integración (esqueleto) servidor MCP productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import os
import respx
import httpx

# Asegura que la raíz del repositorio esté en sys.path cuando se ejecuta pytest desde subdirectorios.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.products_server.main import app  # noqa: E402
from mcp_servers.products_server.tools import get_product_full_info, PermissionError  # noqa: E402

client = TestClient(app)

# --- Unit tests -----------------------------------------------------------

def test_get_product_full_info_role_denied(monkeypatch):
    """Debe lanzar PermissionError para rol no autorizado."""
    with pytest.raises(PermissionError):
        # Llamada directa (no se mockea httpx ya que el permiso falla antes)
        import asyncio
        asyncio.run(get_product_full_info(sku="X", user_role="viewer"))


# --- Integration tests ----------------------------------------------------

@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    # Reset de variables en cada test
    monkeypatch.setenv("MCP_CACHE_TTL_SECONDS", "2")
    monkeypatch.delenv("MCP_REQUIRE_TOKEN", raising=False)
    monkeypatch.delenv("MCP_SHARED_TOKEN", raising=False)
    yield


def test_invoke_tool_basic_flow():
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "ABC123",
                "name": "Producto Demo",
                "sale_price": 10.5,
                "stock": 7,
            })
        )
        payload = {
            "tool_name": "get_product_info",
            "parameters": {"sku": "ABC123", "user_role": "viewer"},
        }
        response = client.post("/invoke_tool", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == "get_product_info"
        assert data["result"]["sku"] == "ABC123"
        assert route.called


def test_cache_second_call_hits_cache(monkeypatch):
    monkeypatch.setenv("MCP_CACHE_TTL_SECONDS", "5")
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "SKU1",
                "name": "Producto Cache",
                "sale_price": 1.0,
                "stock": 1,
            })
        )
        payload = {"tool_name": "get_product_info", "parameters": {"sku": "SKU1", "user_role": "viewer"}}
        r1 = client.post("/invoke_tool", json=payload)
        assert r1.status_code == 200
        assert route.call_count == 1
        r2 = client.post("/invoke_tool", json=payload)
        assert r2.status_code == 200
        # No se realizó nueva llamada HTTP si cache funcionó
        assert route.call_count == 1


def test_token_required_rejects_without_header(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_TOKEN", "1")
    monkeypatch.setenv("MCP_SHARED_TOKEN", "secret123")
    payload = {"tool_name": "get_product_info", "parameters": {"sku": "A", "user_role": "viewer"}}
    resp = client.post("/invoke_tool", json=payload)
    assert resp.status_code == 401


def test_token_required_accepts_with_header(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_TOKEN", "1")
    monkeypatch.setenv("MCP_SHARED_TOKEN", "secret123")
    with respx.mock(base_url="http://api:8000") as router:
        router.get("/variants/lookup").mock(return_value=httpx.Response(200, json={"sku": "B", "name": "NB", "sale_price": 2, "stock": 5}))
        payload = {"tool_name": "get_product_info", "parameters": {"sku": "B", "user_role": "viewer"}}
        resp = client.post("/invoke_tool", json=payload, headers={"X-MCP-Token": "secret123"})
        assert resp.status_code == 200
        assert resp.json()["result"]["sku"] == "B"
