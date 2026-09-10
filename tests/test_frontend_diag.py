#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_frontend_diag.py
# NG-HEADER: Ubicación: tests/test_frontend_diag.py
# NG-HEADER: Descripción: Test endpoint diagnóstico frontend
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient
from services.api import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_frontend_diag_no_se_monta_fuera_de_desarrollo(client):
    assert client.get("/debug/frontend/diag").status_code == 404


def test_frontend_ping_auth_no_se_monta_fuera_de_desarrollo(client):
    assert client.get("/debug/frontend/ping-auth").status_code == 404


def test_frontend_env_no_se_expone(client):
    assert client.get("/debug/frontend/env").status_code == 404


def test_frontend_log_error_no_se_monta_fuera_de_desarrollo(client):
    payload = {
        "message": "Test error desde test_frontend_log_error",
        "stack": "FakeStack:line1\nline2",
        "component_stack": "<App /> -> <X />",
        "user_agent": "pytest-agent",
    }
    r = client.post("/debug/frontend/log-error", json=payload)
    assert r.status_code == 404


def test_debug_general_no_se_monta_fuera_de_desarrollo(client):
    assert client.get("/debug/config").status_code == 404
