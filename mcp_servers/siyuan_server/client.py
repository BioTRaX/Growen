#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: client.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/client.py
# NG-HEADER: Descripción: Cliente HTTP seguro y tipado para la API de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx


class SiYuanError(RuntimeError):
    """Error seguro y estable expuesto por la integración."""


class SiYuanAPIError(SiYuanError):
    pass


class SiYuanAuthenticationError(SiYuanError):
    pass


class SiYuanRateLimitError(SiYuanError):
    pass


class SiYuanTimeoutError(SiYuanError):
    pass


class SiYuanNetworkError(SiYuanError):
    pass


class SiYuanConfigurationError(SiYuanError):
    pass


class SiYuanClient:
    """Cliente mínimo para endpoints públicos y estables de la API de SiYuan."""

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: Callable[[], str],
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0)),
            transport=transport,
            trust_env=False,
        )

    async def __aenter__(self) -> "SiYuanClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        retry_read: bool = False,
    ) -> Any:
        token = self._token_provider().strip()
        if not token:
            raise SiYuanConfigurationError("siyuan_token_missing")
        attempts = 2 if retry_read else 1
        for attempt in range(attempts):
            try:
                response = await self._client.post(
                    f"{self._base_url}/{endpoint.lstrip('/')}",
                    json=payload,
                    headers={"Authorization": f"Token {token}"},
                )
                if response.status_code in {401, 403}:
                    raise SiYuanAuthenticationError("siyuan_authentication_failed")
                if response.status_code == 429:
                    raise SiYuanRateLimitError("siyuan_rate_limited")
                response.raise_for_status()
                try:
                    envelope = response.json()
                except ValueError as exc:
                    raise SiYuanAPIError("siyuan_invalid_response") from exc
                if not isinstance(envelope, dict) or envelope.get("code") != 0:
                    raise SiYuanAPIError("siyuan_api_error")
                return envelope.get("data")
            except httpx.TimeoutException as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise SiYuanTimeoutError("siyuan_timeout") from exc
            except httpx.RequestError as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.25)
                    continue
                raise SiYuanNetworkError("siyuan_network_error") from exc
        raise SiYuanNetworkError("siyuan_network_error")


__all__ = [
    "SiYuanAPIError",
    "SiYuanAuthenticationError",
    "SiYuanClient",
    "SiYuanConfigurationError",
    "SiYuanError",
    "SiYuanNetworkError",
    "SiYuanRateLimitError",
    "SiYuanTimeoutError",
]
