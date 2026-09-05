#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_oauth_webhooks.py
# NG-HEADER: Ubicación: tests/test_meli_oauth_webhooks.py
# NG-HEADER: Descripción: Pruebas de OAuth PKCE y recepción durable de webhooks MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from db.models import MeliAccount, MeliNotification, MeliOAuthState, MeliSyncJob
from services.meli.crypto import TokenCipher
from services.meli.settings import MeliRuntimeConfig


def runtime_config() -> MeliRuntimeConfig:
    return MeliRuntimeConfig(
        app_id=SecretStr("123456"),
        client_secret=SecretStr("client-secret-de-prueba"),
        token_encryption_key=SecretStr("unused"),
        redirect_uri="https://meli.example.test/integrations/meli/oauth/callback",
        api_base_url="https://api.mercadolibre.com",
        authorization_url="https://auth.mercadolibre.com.ar/authorization",
        allowed_topics=frozenset({"items", "questions", "messages", "orders_v2"}),
        request_timeout_seconds=5.0,
        webhook_max_bytes=65_536,
        oauth_state_ttl_seconds=600,
    )


@pytest.mark.asyncio
async def test_authorization_persists_only_state_hash_and_pkce_ciphertext(db_session) -> None:
    """Detecta persistencia accidental de state o code_verifier en texto claro."""
    from services.meli.oauth import create_authorization

    cipher = TokenCipher(b"k" * 32)
    authorization = await create_authorization(db_session, requested_by_user_id=None, config=runtime_config(), cipher=cipher)

    row = await db_session.scalar(select(MeliOAuthState))
    assert row is not None
    assert authorization.state not in row.state_hash
    assert authorization.code_verifier not in row.code_verifier_ciphertext
    assert "code_challenge_method=S256" in authorization.authorization_url
    assert "code_verifier" not in authorization.authorization_url
    assert set(parse_qs(urlparse(authorization.authorization_url).query)["scope"][0].split()) == {"read", "write", "offline_access"}


class FakeMeliClient:
    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> dict:
        assert code == "authorization-code"
        assert redirect_uri == runtime_config().redirect_uri
        assert len(code_verifier) >= 43
        return {
            "access_token": "access-opaco",
            "refresh_token": "refresh-opaco",
            "expires_in": 10_800,
            "scope": "read write offline_access",
            "user_id": 42,
        }

    async def get_me(self, access_token: str) -> dict:
        assert access_token == "access-opaco"
        return {"id": 42, "site_id": "MLA"}


@pytest.mark.asyncio
async def test_callback_consumes_state_once_and_encrypts_tokens(db_session) -> None:
    """Detecta replay del callback o almacenamiento de tokens en claro."""
    from services.meli.oauth import MeliOAuthError, complete_authorization, create_authorization

    cipher = TokenCipher(b"k" * 32)
    authorization = await create_authorization(db_session, requested_by_user_id=None, config=runtime_config(), cipher=cipher)
    account = await complete_authorization(
        db_session,
        state=authorization.state,
        code="authorization-code",
        config=runtime_config(),
        cipher=cipher,
        client=FakeMeliClient(),
    )

    assert account.seller_id == 42
    assert "access-opaco" not in account.access_token_ciphertext
    assert cipher.decrypt(account.access_token_ciphertext, purpose="access", account_ref="42") == "access-opaco"
    with pytest.raises(MeliOAuthError, match="meli_oauth_state_already_used"):
        await complete_authorization(
            db_session,
            state=authorization.state,
            code="authorization-code",
            config=runtime_config(),
            cipher=cipher,
            client=FakeMeliClient(),
        )


@pytest.mark.asyncio
async def test_webhook_is_deduplicated_and_creates_one_durable_job(db_session) -> None:
    """Detecta doble procesamiento cuando MeLi reintenta la misma notificación."""
    from services.meli.webhooks import ingest_notification

    account = MeliAccount(
        application_id="123456",
        seller_id=42,
        access_token_ciphertext="cipher-a",
        refresh_token_ciphertext="cipher-r",
        token_expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(account)
    await db_session.commit()
    payload = {
        "_id": "notification-1",
        "resource": "/items/MLA123",
        "user_id": 42,
        "topic": "items",
        "application_id": 123456,
        "attempts": 1,
        "sent": "2026-08-31T12:00:00Z",
    }

    first = await ingest_notification(db_session, payload=payload, config=runtime_config())
    second = await ingest_notification(db_session, payload=payload, config=runtime_config())

    assert first.duplicate is False
    assert second.duplicate is True
    assert len(list((await db_session.execute(select(MeliNotification))).scalars())) == 1
    assert len(list((await db_session.execute(select(MeliSyncJob))).scalars())) == 1


@pytest.mark.asyncio
async def test_webhook_rejects_absolute_or_unapproved_resource(db_session) -> None:
    """Detecta SSRF si el worker aceptara una URL arbitraria del webhook."""
    from services.meli.webhooks import MeliWebhookError, ingest_notification

    payload = {
        "_id": "notification-evil",
        "resource": "https://evil.example/steal",
        "user_id": 42,
        "topic": "items",
        "application_id": 123456,
    }
    with pytest.raises(MeliWebhookError, match="meli_webhook_resource_invalid"):
        await ingest_notification(db_session, payload=payload, config=runtime_config())
