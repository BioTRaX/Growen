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


def test_get_product_full_info_includes_enrichment_fields():
    """Verifica que get_product_full_info incluye technical_specs y usage_instructions cuando están presentes."""
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "PROD-RICH",
                "name": "Producto Enriquecido",
                "sale_price": 100.0,
                "stock": 10,
                "technical_specs": {
                    "dimensions": {"height": "50 cm", "width": "30 cm"},
                    "power": "1000W",
                    "weight": "5.2 kg"
                },
                "usage_instructions": {
                    "steps": ["Paso 1: Lavar", "Paso 2: Conectar"],
                    "tips": "Usar con precaución"
                }
            })
        )
        payload = {
            "tool_name": "get_product_full_info",
            "parameters": {"sku": "PROD-RICH", "user_role": "admin"},
        }
        response = client.post("/invoke_tool", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == "get_product_full_info"
        result = data["result"]
        assert result["sku"] == "PROD-RICH"
        # Verificar que incluye campos de enriquecimiento
        assert "technical_specs" in result
        assert result["technical_specs"]["power"] == "1000W"
        assert "usage_instructions" in result
        assert len(result["usage_instructions"]["steps"]) == 2
        assert route.called


def test_get_product_full_info_omits_empty_enrichment_fields():
    """Verifica que get_product_full_info omite technical_specs/usage_instructions si están vacíos o nulos."""
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "PROD-BASIC",
                "name": "Producto Sin Enriquecer",
                "sale_price": 50.0,
                "stock": 5,
                "technical_specs": None,
                "usage_instructions": {}
            })
        )
        payload = {
            "tool_name": "get_product_full_info",
            "parameters": {"sku": "PROD-BASIC", "user_role": "colaborador"},
        }
        response = client.post("/invoke_tool", json=payload)
        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["sku"] == "PROD-BASIC"
        # Verificar que NO incluye campos vacíos (optimización de tokens)
        assert "technical_specs" not in result
        assert "usage_instructions" not in result
        assert route.called


def test_get_product_info_excludes_enrichment_fields():
    """Verifica que get_product_info (versión ligera) NO incluye campos de enriquecimiento."""
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "PROD-LIGHT",
                "name": "Producto Ligero",
                "sale_price": 25.0,
                "stock": 3,
                "technical_specs": {"power": "500W"},
                "usage_instructions": {"steps": ["Paso 1"]}
            })
        )
        payload = {
            "tool_name": "get_product_info",
            "parameters": {"sku": "PROD-LIGHT", "user_role": "viewer"},
        }
        response = client.post("/invoke_tool", json=payload)
        assert response.status_code == 200
        data = response.json()
        result = data["result"]
        assert result["sku"] == "PROD-LIGHT"
        # Verificar que NO incluye campos de enriquecimiento (versión ligera)
        assert "technical_specs" not in result
        assert "usage_instructions" not in result
        assert route.called

