#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: client.py
# NG-HEADER: Ubicación: services/meli/client.py
# NG-HEADER: Descripción: Cliente HTTP acotado para la API oficial de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Cliente sin redirects ni credenciales en query strings."""

from __future__ import annotations

from typing import Any

import httpx

from services.meli.settings import MeliRuntimeConfig


class MeliAPIError(RuntimeError):
    def __init__(self, code: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class MeliClient:
    def __init__(self, config: MeliRuntimeConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base_url,
            timeout=config.request_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _json(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 429:
            raise MeliAPIError("meli_rate_limited", status_code=429, retryable=True)
        if response.status_code == 401:
            raise MeliAPIError("meli_unauthorized", status_code=401)
        if response.status_code >= 500:
            raise MeliAPIError("meli_upstream_unavailable", status_code=response.status_code, retryable=True)
        if response.status_code >= 400:
            raise MeliAPIError("meli_request_rejected", status_code=response.status_code)
        try:
            value = response.json()
        except ValueError as exc:
            raise MeliAPIError("meli_response_invalid") from exc
        if not isinstance(value, dict):
            raise MeliAPIError("meli_response_invalid")
        return value

    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
        response = await self._client.post(
            "/oauth/token",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": self.config.app_id.get_secret_value(),
                "client_secret": self.config.client_secret.get_secret_value(),
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        return await self._json(response)

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        response = await self._client.post(
            "/oauth/token",
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": self.config.app_id.get_secret_value(),
                "client_secret": self.config.client_secret.get_secret_value(),
                "refresh_token": refresh_token,
            },
        )
        return await self._json(response)

    async def get_me(self, access_token: str) -> dict[str, Any]:
        return await self.get_resource("/users/me", access_token)

    async def get_resource(self, resource: str, access_token: str) -> dict[str, Any]:
        if not resource.startswith("/") or ".." in resource or "://" in resource:
            raise MeliAPIError("meli_resource_invalid")
        response = await self._client.get(resource, headers={"Authorization": f"Bearer {access_token}"})
        return await self._json(response)

    async def update_item(self, item_id: str, payload: dict[str, Any], access_token: str) -> dict[str, Any]:
        response = await self._client.put(
            f"/items/{item_id}",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
        )
        return await self._json(response)
