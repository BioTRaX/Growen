#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_frontend_diag.py
# NG-HEADER: Ubicación: tests/test_frontend_diag.py
# NG-HEADER: Descripción: Test endpoint diagnóstico frontend
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient
from services.api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_frontend_diag_endpoint(client):
    r = client.get("/debug/frontend/diag")
    assert r.status_code == 200
    data = r.json()
    # Debe contener claves básicas
    for k in ["build_present", "assets_count", "api_base_url", "notes"]:
        assert k in data
    assert isinstance(data["notes"], list)


def test_frontend_ping_auth(client):
    r = client.get("/debug/frontend/ping-auth")
    assert r.status_code == 200
    data = r.json()
    assert "auth_request_ok" in data
    assert "cookies_present" in data
    assert "auth" in data


def test_frontend_env(client):
    r = client.get("/debug/frontend/env")
    assert r.status_code == 200
    data = r.json()
    assert "env" in data and isinstance(data["env"], dict)
    assert "count" in data


def test_frontend_log_error(client):
    payload = {
        "message": "Test error desde test_frontend_log_error",
        "stack": "FakeStack:line1\nline2",
        "component_stack": "<App /> -> <X />",
        "user_agent": "pytest-agent",
    }
    r = client.post("/debug/frontend/log-error", json=payload)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"