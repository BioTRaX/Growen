#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_admin_operations_security.py
# NG-HEADER: Ubicación: tests/test_admin_operations_security.py
# NG-HEADER: Descripción: Regresión de sesión, roles, CSRF y WebSocket en operaciones administrativas.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from db.models import User
from services.api import app
from services.auth import hash_pw


async def _user(db, identifier: str, role: str) -> User:
    user = User(identifier=identifier, password_hash=hash_pw("segura-test-123"), role=role)
    db.add(user)
    await db.commit()
    return user


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_scheduler_exige_csrf_y_rol_admin(db_session):
    admin = await _user(db_session, "admin-operations", "admin")
    with TestClient(app) as client:
        assert client.post("/auth/login", json={"identifier": admin.identifier, "password": "segura-test-123"}).status_code == 200
        payload = {
            "start_hour": "03:00",
            "interval_hours": 12,
            "timezone": "America/Argentina/Buenos_Aires",
            "update_frequency_days": 3,
            "max_products_per_run": 25,
            "prioritize_mandatory": True,
        }
        assert client.post("/admin/scheduler/config", json=payload).status_code == 403
        csrf = client.cookies.get("csrf_token")
        assert client.post("/admin/scheduler/config", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_colaborador_no_administra_conocimiento(db_session):
    collaborator = await _user(db_session, "collab-operations", "colaborador")
    with TestClient(app) as client:
        assert client.post("/auth/login", json={"identifier": collaborator.identifier, "password": "segura-test-123"}).status_code == 200
        assert client.get("/admin/knowledge/status").status_code == 403


@pytest.mark.no_auth_override
def test_websocket_drive_rechaza_anonimos():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/admin/drive-sync/ws"):
                pass
        assert rejected.value.code == 4403
