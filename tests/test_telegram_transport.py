#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_telegram_transport.py
# NG-HEADER: Ubicación: tests/test_telegram_transport.py
# NG-HEADER: Descripción: Pruebas del cierre de webhook y transporte único Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest
from fastapi import HTTPException

from agent_core.config import Settings, settings
from db.models import User
from services.api import app
from services.auth import SessionData
from services.routers import admin_chat
from services.routers.external_identities import LinkRequestInput, telegram_link_request, telegram_linking_status


def test_telegram_webhook_is_not_exposed() -> None:
    paths = {path for route in app.routes if (path := getattr(route, "path", None))}
    assert "/telegram/webhook/{token}" not in paths


def test_telegram_transport_rejects_webhook() -> None:
    with pytest.raises(RuntimeError, match="sólo admite polling"):
        Settings(telegram_transport="webhook")


def test_missing_worker_health_is_safe(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(admin_chat, "TELEGRAM_HEALTH_FILE", tmp_path / "missing.json")
    health = admin_chat._read_telegram_worker_health()
    assert health["status"] == "not_running"
    assert health["backlog"] == 0
    assert "token" not in health


def test_worker_health_only_returns_allowlisted_fields(monkeypatch, tmp_path) -> None:
    health_file = tmp_path / "telegram_health.json"
    health_file.write_text(
        '{"status":"running","backlog":3,"processed":8,"token":"secret","message":"private"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_chat, "TELEGRAM_HEALTH_FILE", health_file)
    health = admin_chat._read_telegram_worker_health()
    assert health["status"] == "running"
    assert health["backlog"] == 3
    assert health["processed"] == 8
    assert "token" not in health
    assert "message" not in health


@pytest.mark.asyncio
async def test_link_request_is_closed_while_flags_are_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_role_linking_enabled", False)
    session = SessionData(session=None, user=User(id=9, identifier="client", role="cliente", password_hash="unused"), role="cliente")
    status = await telegram_linking_status(session)
    assert status["enabled"] is False
    with pytest.raises(HTTPException) as error:
        await telegram_link_request(LinkRequestInput(password="unused"), session, None)  # type: ignore[arg-type]
    assert error.value.status_code == 409
    assert error.value.detail == "telegram_linking_disabled"
