#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_gateway.py
# NG-HEADER: Ubicación: tests/test_meli_gateway.py
# NG-HEADER: Descripción: Pruebas de la superficie pública mínima del gateway MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime

from pydantic import SecretStr
import httpx
import pytest


@pytest.mark.asyncio
async def test_callback_logs_safe_failure_without_oauth_values(db_session, monkeypatch, caplog):
    from services.meli import app as gateway

    async def fail(*args, **kwargs):
        raise KeyError("refresh_token")

    monkeypatch.setattr(gateway, "complete_authorization", fail)
    app = gateway.create_meli_app(config=_config(), cipher=TokenCipher(b"g" * 32), client=object())

    async def session_override():
        yield db_session

    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway") as client:
        response = await client.get("/integrations/meli/oauth/callback", params={"code": "private-code", "state": "private-state"})
    assert response.status_code == 400
    assert "acceso sin conexión" in response.text
    assert "vencida" not in response.text
    records = [record for record in caplog.records if record.name == "services.meli.app"]
    assert len(records) == 1
    assert "missing_refresh_token" in records[0].getMessage()
    assert "private-code" not in records[0].getMessage()
    assert "private-state" not in records[0].getMessage()

from db.models import MeliAccount
from db.session import get_session
from services.meli.crypto import TokenCipher
from services.meli.settings import MeliRuntimeConfig


def _config() -> MeliRuntimeConfig:
    return MeliRuntimeConfig(
        app_id=SecretStr("123456"),
        client_secret=SecretStr("secreto"),
        token_encryption_key=SecretStr("unused"),
        redirect_uri="https://meli.example.test/integrations/meli/oauth/callback",
        api_base_url="https://api.mercadolibre.com",
        authorization_url="https://auth.mercadolibre.com.ar/authorization",
        allowed_topics=frozenset({"items", "questions"}),
        request_timeout_seconds=10,
        webhook_max_bytes=1024,
        oauth_state_ttl_seconds=600,
    )


@pytest.mark.asyncio
async def test_gateway_exposes_only_health_callback_and_webhook(db_session) -> None:
    from services.meli.app import create_meli_app

    app = create_meli_app(config=_config(), cipher=TokenCipher(b"g" * 32), client=object())

    async def session_override():
        yield db_session

    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        assert (await client.get("/health/live")).status_code == 200
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/anything-else")).status_code == 404


@pytest.mark.asyncio
async def test_webhook_accepts_and_deduplicates_valid_notice(db_session) -> None:
    from services.meli.app import create_meli_app

    db_session.add(
        MeliAccount(
            application_id="123456",
            seller_id=42,
            access_token_ciphertext="a",
            refresh_token_ciphertext="r",
            token_expires_at=datetime(2099, 1, 1),
        )
    )
    await db_session.commit()
    app = create_meli_app(config=_config(), cipher=TokenCipher(b"g" * 32), client=object())

    async def session_override():
        yield db_session

    app.dependency_overrides[get_session] = session_override
    payload = {
        "_id": "notice-gateway-1",
        "resource": "/items/MLA123",
        "user_id": 42,
        "topic": "items",
        "application_id": 123456,
        "attempts": 1,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        first = await client.post("/integrations/meli/webhook", json=payload)
        second = await client.post("/integrations/meli/webhook", json=payload)
    assert first.status_code == 200
    assert first.json() == {"accepted": True, "duplicate": False}
    assert second.json() == {"accepted": True, "duplicate": True}


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_content_type_and_large_body(db_session) -> None:
    from services.meli.app import create_meli_app

    app = create_meli_app(config=_config(), cipher=TokenCipher(b"g" * 32), client=object())

    async def session_override():
        yield db_session

    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        wrong_type = await client.post("/integrations/meli/webhook", content=b"{}")
        too_large = await client.post(
            "/integrations/meli/webhook",
            content=b"{" + b" " * 1100 + b"}",
            headers={"content-type": "application/json"},
        )
    assert wrong_type.status_code == 415
    assert too_large.status_code == 413
