#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_auth_session_cookie.py
# NG-HEADER: Ubicación: tests/test_auth_session_cookie.py
# NG-HEADER: Descripción: Regresión del SID crudo usado por las cookies de sesión.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from fastapi.testclient import TestClient

from db.models import User
from services.api import app
from services.auth import hash_pw


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_login_cookie_resuelve_la_sesion_real(db_session):
    user = User(
        identifier="admin-cookie-test",
        password_hash=hash_pw("segura-test-123"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"identifier": user.identifier, "password": "segura-test-123"},
        )
        assert login.status_code == 200

        current = client.get("/auth/me")
        assert current.status_code == 200
        assert current.json()["is_authenticated"] is True
        assert current.json()["role"] == "admin"

        csrf = client.cookies.get("csrf_token")
        created = client.post(
            "/suppliers",
            headers={"X-CSRF-Token": csrf},
            json={"slug": "sesion-real", "name": "Sesión Real"},
        )
        assert created.status_code == 200
