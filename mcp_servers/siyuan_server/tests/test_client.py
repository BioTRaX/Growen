#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_client.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/tests/test_client.py
# NG-HEADER: Descripción: Pruebas del cliente seguro para la API de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import importlib

import httpx
import pytest


client_module = importlib.import_module("mcp_servers.siyuan_server.client")


def test_client_module_exists() -> None:
    assert client_module is not None


def _client(handler):
    transport = httpx.MockTransport(handler)
    return client_module.SiYuanClient(
        base_url="http://localhost:6806/",
        token_provider=lambda: "api-secret-token",
        transport=transport,
    )


@pytest.mark.asyncio
async def test_post_uses_official_token_header_and_normalized_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:6806/api/notebook/lsNotebooks"
        assert request.headers["Authorization"] == "Token api-secret-token"
        return httpx.Response(200, json={"code": 0, "msg": "", "data": {"notebooks": []}})

    async with _client(handler) as client:
        data = await client.post("/api/notebook/lsNotebooks", {})

    assert data == {"notebooks": []}


@pytest.mark.asyncio
async def test_post_rejects_nonzero_siyuan_envelope_without_leaking_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": -1, "msg": "token=secret", "data": None})

    async with _client(handler) as client:
        with pytest.raises(client_module.SiYuanAPIError, match="siyuan_api_error") as caught:
            await client.post("/api/notebook/lsNotebooks", {})

    assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_read_retries_once_after_transient_timeout() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"code": 0, "msg": "", "data": {"ok": True}})

    async with _client(handler) as client:
        data = await client.post("/api/export/exportMdContent", {"id": "doc"}, retry_read=True)

    assert attempts == 2
    assert data == {"ok": True}


@pytest.mark.asyncio
async def test_write_does_not_retry_after_timeout() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow", request=request)

    async with _client(handler) as client:
        with pytest.raises(client_module.SiYuanTimeoutError, match="siyuan_timeout"):
            await client.post("/api/filetree/createDocWithMd", {"path": "/Growen/Test"})

    assert attempts == 1


@pytest.mark.asyncio
async def test_post_maps_authentication_failure_to_safe_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="sensitive upstream response")

    async with _client(handler) as client:
        with pytest.raises(client_module.SiYuanAuthenticationError, match="siyuan_authentication_failed") as caught:
            await client.post("/api/notebook/lsNotebooks", {})

    assert "sensitive" not in str(caught.value)
