#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_client.py
# NG-HEADER: Ubicación: tests/test_meli_client.py
# NG-HEADER: Descripción: Pruebas del transporte HTTP seguro hacia Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
from pydantic import SecretStr
import pytest

from services.meli.client import MeliAPIError, MeliClient
from services.meli.settings import MeliRuntimeConfig


def _config() -> MeliRuntimeConfig:
    return MeliRuntimeConfig(
        app_id=SecretStr("app-test"),
        client_secret=SecretStr("secret-test"),
        token_encryption_key=SecretStr("unused"),
        redirect_uri="https://meli.example.test/integrations/meli/oauth/callback",
        api_base_url="https://api.mercadolibre.com",
        authorization_url="https://auth.mercadolibre.com.ar/authorization",
        allowed_topics=frozenset({"items"}),
        request_timeout_seconds=5,
        webhook_max_bytes=4096,
        oauth_state_ttl_seconds=600,
    )


@pytest.mark.asyncio
async def test_oauth_secret_is_sent_in_form_not_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b""
        form = parse_qs(request.content.decode())
        assert form["client_secret"] == ["secret-test"]
        assert form["code_verifier"] == ["verifier-test"]
        return httpx.Response(200, json={"access_token": "opaque"})

    client = MeliClient(_config(), transport=httpx.MockTransport(handler))
    try:
        await client.exchange_code(
            code="code-test",
            redirect_uri=_config().redirect_uri,
            code_verifier="verifier-test",
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_resource_uses_bearer_and_429_is_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer opaque-token"
        return httpx.Response(429, json={"message": "rate limit"})

    client = MeliClient(_config(), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MeliAPIError) as rejected:
            await client.get_resource("/items/MLA123", "opaque-token")
    finally:
        await client.aclose()
    assert rejected.value.retryable is True
    assert rejected.value.code == "meli_rate_limited"
