#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_ws_role_refresh.py
# NG-HEADER: Ubicación: tests/test_ws_role_refresh.py
# NG-HEADER: Descripción: Prueba que WebSocket recarga el rol vigente por mensaje.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from db.models import Session as DBSess, User
from services.auth import hash_session_id
from services.routers.ws import _load_active_session


@pytest.mark.asyncio
async def test_load_active_session_observes_role_changes(db_session) -> None:
    user = User(identifier="ws-live-role", password_hash="x", role="cliente")
    db_session.add(user)
    await db_session.flush()
    db_session.add(DBSess(
        id=hash_session_id("ws-live-sid"),
        user_id=user.id,
        role="cliente",
        csrf_token="csrf",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    ))
    await db_session.commit()

    first = await _load_active_session(db_session, "ws-live-sid")
    assert first is not None and first.user is not None
    assert first.user.role == "cliente"

    user.role = "colaborador"
    await db_session.commit()
    second = await _load_active_session(db_session, "ws-live-sid")
    assert second is not None and second.user is not None
    assert second.user.role == "colaborador"
