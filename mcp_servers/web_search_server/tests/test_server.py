#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_server.py
# NG-HEADER: Ubicación: mcp_servers/web_search_server/tests/test_server.py
# NG-HEADER: Descripción: Pruebas de seguridad y compatibilidad de MCP Web Search.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from mcp_servers.security import reset_rate_limit
from mcp_servers.web_search_server.main import app

SECRET = "test-mcp-web-secret-at-least-32-bytes-long"
client = TestClient(app)


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setenv("MCP_SECRET_KEY", SECRET)
    monkeypatch.setenv("MCP_JWT_ISSUER", "growen-api")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "growen-mcp")
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MINUTE", "60")
    monkeypatch.setenv("MCP_LEGACY_RPC_ENABLED", "1")
    reset_rate_limit()


def token(role: str = "admin", expires_delta: timedelta = timedelta(minutes=5)) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "web-test",
            "role": role,
            "iat": now,
            "exp": now + expires_delta,
            "jti": "web-test-jti",
            "iss": "growen-api",
            "aud": "growen-mcp",
        },
        SECRET,
        algorithm="HS256",
    )


def test_legacy_requires_token():
    response = client.post(
        "/invoke_tool",
        json={"tool_name": "search_web", "parameters": {"query": "growen"}},
    )
    assert response.status_code == 401


def test_legacy_rejects_guest():
    response = client.post(
        "/invoke_tool",
        json={"tool_name": "search_web", "parameters": {"query": "growen"}},
        headers={"Authorization": f"Bearer {token('guest')}"},
    )
    assert response.status_code == 403


def test_legacy_rejects_expired_token():
    response = client.post(
        "/invoke_tool",
        json={"tool_name": "search_web", "parameters": {"query": "growen"}},
        headers={"Authorization": f"Bearer {token(expires_delta=timedelta(seconds=-1))}"},
    )
    assert response.status_code == 401


def test_legacy_rejects_invalid_token():
    response = client.post(
        "/invoke_tool",
        json={"tool_name": "search_web", "parameters": {"query": "growen"}},
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


def test_health_describes_mcp_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["endpoint"] == "/mcp"


def test_guest_does_not_discover_web_search_tool():
    headers = {
        "Authorization": f"Bearer {token('guest')}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    with TestClient(app, base_url="http://localhost") as mcp_client:
        listed = mcp_client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=headers,
        )
        assert listed.status_code == 200
        assert listed.json()["result"]["tools"] == []
