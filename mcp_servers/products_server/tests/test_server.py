#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_server.py
# NG-HEADER: Ubicación: mcp_servers/products_server/tests/test_server.py
# NG-HEADER: Descripción: Pruebas unitarias e integración servidor MCP productos con auth JWT
# NG-HEADER: Lineamientos: Ver AGENTS.md

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import respx
import httpx
import jwt
from datetime import datetime, timedelta, timezone

# Asegura que la raíz del repositorio esté en sys.path cuando se ejecuta pytest desde subdirectorios.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers.products_server.main import app  # noqa: E402
from mcp_servers.products_server.security import (  # noqa: E402
    verify_mcp_token,
    MCPTokenExpired,
    MCPTokenInvalid,
    reset_rate_limit,
)

client = TestClient(app)

# --- Test Fixtures ---

TEST_SECRET = "test-mcp-secret-key-for-testing-only-32-bytes"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Setup base environment for tests."""
    monkeypatch.setenv("MCP_CACHE_TTL_SECONDS", "2")
    monkeypatch.setenv("MCP_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MINUTE", "60")
    monkeypatch.setenv("MCP_JWT_ISSUER", "growen-api")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "growen-mcp")
    monkeypatch.setenv("MCP_LEGACY_RPC_ENABLED", "1")
    # Reset rate limits between tests
    reset_rate_limit()
    # Clear cache between tests to prevent interference
    from mcp_servers.products_server.tools import _cache
    _cache.clear()
    yield



def create_test_token(
    sub: str = "test_user",
    role: str = "admin",
    expires_delta: timedelta | None = None,
    secret: str = TEST_SECRET,
) -> str:
    """Create a test JWT token."""
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=5))
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": expires,
        "jti": "test-jti",
        "iss": "growen-api",
        "aud": "growen-mcp",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# --- Unit tests: Security Module ---

def test_verify_token_valid():
    """Debe validar token válido correctamente."""
    token = create_test_token()
    claims = verify_mcp_token(token)
    assert claims.sub == "test_user"
    assert claims.role == "admin"


def test_verify_token_expired():
    """Debe rechazar token expirado."""
    token = create_test_token(expires_delta=timedelta(seconds=-10))
    with pytest.raises(MCPTokenExpired):
        verify_mcp_token(token)


def test_verify_token_invalid_signature():
    """Debe rechazar token con firma inválida."""
    token = create_test_token(secret="wrong-secret-that-is-at-least-32-bytes")
    with pytest.raises(MCPTokenInvalid):
        verify_mcp_token(token)


def test_verify_token_malformed():
    """Debe rechazar token malformado."""
    with pytest.raises(MCPTokenInvalid):
        verify_mcp_token("not-a-valid-jwt")


# --- Integration tests: API Endpoint ---

def test_invoke_without_token_returns_401():
    """Petición sin token debe retornar 401."""
    payload = {
        "tool_name": "get_product_info",
        "parameters": {"sku": "ABC123"},
    }
    response = client.post("/invoke_tool", json=payload)
    assert response.status_code == 401
    assert "Token MCP requerido" in response.json()["detail"]


def test_invoke_with_invalid_token_returns_401():
    """Petición con token inválido debe retornar 401."""
    payload = {
        "tool_name": "get_product_info",
        "parameters": {"sku": "ABC123"},
    }
    response = client.post(
        "/invoke_tool",
        json=payload,
        headers={"X-MCP-Token": "invalid-token"},
    )
    assert response.status_code == 401


def test_invoke_with_expired_token_returns_401():
    """Petición con token expirado debe retornar 401."""
    token = create_test_token(expires_delta=timedelta(seconds=-10))
    payload = {
        "tool_name": "get_product_info",
        "parameters": {"sku": "ABC123"},
    }
    response = client.post(
        "/invoke_tool",
        json=payload,
        headers={"X-MCP-Token": token},
    )
    assert response.status_code == 401
    assert "expir" in response.json()["detail"].lower()


def test_invoke_tool_basic_flow():
    """Petición con token válido debe ejecutar tool correctamente."""
    token = create_test_token()
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
            "parameters": {"sku": "ABC123"},
        }
        response = client.post(
            "/invoke_tool",
            json=payload,
            headers={"X-MCP-Token": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == "get_product_info"
        assert data["result"]["sku"] == "ABC123"
        assert route.called


def test_cache_second_call_hits_cache(monkeypatch):
    """Segunda llamada debe usar cache."""
    monkeypatch.setenv("MCP_CACHE_TTL_SECONDS", "5")
    token = create_test_token()
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "SKU1",
                "name": "Producto Cache",
                "sale_price": 1.0,
                "stock": 1,
            })
        )
        payload = {"tool_name": "get_product_info", "parameters": {"sku": "SKU1"}}
        r1 = client.post("/invoke_tool", json=payload, headers={"X-MCP-Token": token})
        assert r1.status_code == 200
        assert route.call_count == 1
        r2 = client.post("/invoke_tool", json=payload, headers={"X-MCP-Token": token})
        assert r2.status_code == 200
        # No se realizó nueva llamada HTTP si cache funcionó
        assert route.call_count == 1


def test_get_product_full_info_requires_admin_role():
    """get_product_full_info debe requerir rol admin o colaborador."""
    token_admin = create_test_token(role="admin")
    token_colaborador = create_test_token(role="colaborador")
    
    with respx.mock(base_url="http://api:8000") as router:
        router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "PROD-RICH",
                "name": "Producto Enriquecido",
                "sale_price": 100.0,
                "stock": 10,
                "tags": ["#Interior", "#Orgánico"],
            })
        )
        payload = {
            "tool_name": "get_product_full_info",
            "parameters": {"sku": "PROD-RICH"},
        }
        
        # Admin puede acceder
        response_admin = client.post(
            "/invoke_tool", json=payload, headers={"X-MCP-Token": token_admin}
        )
        assert response_admin.status_code == 200
        
        # Colaborador puede acceder
        response_colab = client.post(
            "/invoke_tool", json=payload, headers={"X-MCP-Token": token_colaborador}
        )
        assert response_colab.status_code == 200


def test_get_product_full_info_guest_denied():
    """get_product_full_info debe denegar acceso a guest."""
    token = create_test_token(role="guest")
    payload = {
        "tool_name": "get_product_full_info",
        "parameters": {"sku": "PROD-RICH"},
    }
    response = client.post(
        "/invoke_tool", json=payload, headers={"X-MCP-Token": token}
    )
    assert response.status_code == 403
    assert "autorizado" in response.json()["detail"].lower()


def test_rate_limit_blocks_after_threshold(monkeypatch):
    """Rate limit debe bloquear después de exceder umbral."""
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MINUTE", "3")  # Límite bajo para test
    token = create_test_token()
    reset_rate_limit()
    
    with respx.mock(base_url="http://api:8000") as router:
        router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "RATE",
                "name": "Rate Test",
                "sale_price": 1.0,
                "stock": 1,
            })
        )
        payload = {"tool_name": "get_product_info", "parameters": {"sku": "RATE"}}
        
        # Primeras 3 peticiones deben pasar
        for i in range(3):
            response = client.post(
                "/invoke_tool", json=payload, headers={"X-MCP-Token": token}
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"
        
        # Cuarta petición debe ser bloqueada
        response = client.post(
            "/invoke_tool", json=payload, headers={"X-MCP-Token": token}
        )
        assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"
    assert response.headers["Retry-After"] == "60"


def test_get_product_full_info_includes_enrichment_fields():
    """Verifica que get_product_full_info incluye technical_specs y usage_instructions."""
    token = create_test_token(role="admin")
    with respx.mock(base_url="http://api:8000") as router:
        route = router.get("/variants/lookup").mock(
            return_value=httpx.Response(200, json={
                "sku": "PROD-RICH",
                "name": "Producto Enriquecido",
                "sale_price": 100.0,
                "stock": 10,
                "tags": ["#Interior", "#Orgánico"],
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
            "parameters": {"sku": "PROD-RICH"},
        }
        response = client.post(
            "/invoke_tool", json=payload, headers={"X-MCP-Token": token}
        )
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
        assert result["tags"] == ["#Interior", "#Orgánico"]
        assert route.called


def test_find_products_by_name_works_with_token():
    """find_products_by_name debe funcionar con token válido."""
    token = create_test_token(role="guest")  # Rol público canónico
    with respx.mock(base_url="http://api:8000") as router:
        router.get("/catalog/search").mock(
            return_value=httpx.Response(200, json=[
                {"id": 1, "name": "Producto A", "sku": "SKU_A", "stock": 5, "price": 10.0, "tags": ["#Interior"]},
                {"id": 2, "name": "Producto B", "sku": "SKU_B", "stock": 3, "price": 20.0},
            ])
        )
        payload = {
            "tool_name": "find_products_by_name",
            "parameters": {"query": "Producto"},
        }
        response = client.post(
            "/invoke_tool", json=payload, headers={"X-MCP-Token": token}
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["tags"] == ["#Interior"]
        assert result["items"][1]["tags"] == []


def test_health_endpoint():
    """Health endpoint debe responder ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_streamable_http_requires_bearer_token():
    response = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 401


def test_streamable_http_initializes_and_lists_tools():
    """Valida el contrato MCP real sin pasar por el adaptador `/invoke_tool`."""
    headers = {
        "Authorization": f"Bearer {create_test_token(role='admin')}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "growen-contract-test", "version": "1.0"},
        },
    }
    with TestClient(app, base_url="http://localhost") as mcp_client:
        initialized = mcp_client.post("/mcp/", json=initialize, headers=headers)
        assert initialized.status_code == 200
        assert initialized.json()["result"]["serverInfo"]["name"] == "Growen Products"

        listed = mcp_client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=headers,
        )
        assert listed.status_code == 200
        names = {tool["name"] for tool in listed.json()["result"]["tools"]}
        assert {"find_products_by_name", "get_product_info", "get_product_full_info"} <= names

        guest_headers = {
            **headers,
            "Authorization": f"Bearer {create_test_token(role='guest')}",
        }
        guest_listed = mcp_client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
            headers=guest_headers,
        )
        assert guest_listed.status_code == 200
        guest_names = {tool["name"] for tool in guest_listed.json()["result"]["tools"]}
        assert guest_names == {"find_products_by_name", "get_product_info"}
