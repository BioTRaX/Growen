#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_server.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tests/test_server.py
# NG-HEADER: Descripción: Pruebas contractuales y de autorización del MCP de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib

import jwt
import pytest
from fastapi.testclient import TestClient

from mcp_servers.security import reset_rate_limit


server_module = importlib.import_module("mcp_servers.siyuan_server.server")
main_module = importlib.import_module("mcp_servers.siyuan_server.main")
settings_module = importlib.import_module("mcp_servers.siyuan_server.settings")

SECRET = "test-mcp-siyuan-secret-at-least-32-bytes"


def _token(role: str = "admin", expires: timedelta = timedelta(minutes=5)) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "siyuan-test",
            "role": role,
            "iat": now,
            "exp": now + expires,
            "jti": f"siyuan-{role}",
            "iss": "growen-api",
            "aud": "growen-mcp-siyuan",
        },
        SECRET,
        algorithm="HS256",
        headers={"kid": "siyuan-v1"},
    )


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setenv("MCP_SECRET_KEY", SECRET)
    monkeypatch.setenv("MCP_JWT_ISSUER", "growen-api")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "growen-mcp-siyuan")
    monkeypatch.setenv("MCP_JWT_KEY_ID", "siyuan-v1")
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MINUTE", "60")
    reset_rate_limit()


@pytest.fixture(scope="module")
def http_client():
    with TestClient(main_module.app, base_url="http://localhost") as client:
        yield client


def test_token_loader_prefers_file_and_strips_whitespace(tmp_path, monkeypatch) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setenv("SIYUAN_API_TOKEN", "env-token")
    monkeypatch.setenv("SIYUAN_API_TOKEN_FILE", str(token_file))

    assert settings_module.load_api_token() == "file-token"


def test_mcp_secret_loader_reads_file_without_logging_value(tmp_path, monkeypatch) -> None:
    secret_file = tmp_path / "mcp-secret"
    secret_file.write_text("mcp-file-secret\n", encoding="utf-8")
    monkeypatch.setenv("MCP_SIYUAN_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.delenv("MCP_SIYUAN_SECRET_KEY", raising=False)

    assert settings_module.load_mcp_secret() == "mcp-file-secret"


@pytest.mark.asyncio
async def test_stdio_catalog_exposes_four_annotated_tools() -> None:
    tools = await server_module.mcp.list_tools()
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {
        "list_siyuan_notebooks",
        "search_siyuan_docs",
        "read_siyuan_document",
        "create_siyuan_document",
    }
    assert by_name["search_siyuan_docs"].annotations.readOnlyHint is True
    assert by_name["create_siyuan_document"].annotations.readOnlyHint is False
    assert by_name["create_siyuan_document"].annotations.destructiveHint is False
    assert by_name["create_siyuan_document"].annotations.idempotentHint is False


def test_http_transport_requires_bearer_token(http_client) -> None:
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_http_transport_hides_catalog_from_guest(http_client) -> None:
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Authorization": f"Bearer {_token('guest')}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["tools"] == []


def test_http_transport_exposes_catalog_to_admin(http_client) -> None:
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Authorization": f"Bearer {_token('admin')}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["result"]["tools"]) == 4


def test_http_transport_rejects_expired_token(http_client) -> None:
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={
            "Authorization": f"Bearer {_token(expires=timedelta(seconds=-1))}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


def test_health_reports_degraded_without_exposing_error(monkeypatch, http_client) -> None:
    async def fail_health():
        raise RuntimeError("token=secret")

    monkeypatch.setattr(main_module, "check_siyuan_health", fail_health)
    response = http_client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "service": "mcp_siyuan", "upstream": "unavailable"}
