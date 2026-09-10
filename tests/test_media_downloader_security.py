#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_media_downloader_security.py
# NG-HEADER: Ubicación: tests/test_media_downloader_security.py
# NG-HEADER: Descripción: Regresiones SSRF para descargas remotas de imágenes.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import socket

import pytest

from services.media.downloader import (
    DownloadError,
    _validate_connected_peer,
    _validate_public_destination,
    download_product_image,
)


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,resolved_ip",
    [
        ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
        ("http://db:5432/", "172.20.0.3"),
        ("http://intranet.local/recurso", "192.168.100.20"),
        ("http://[::1]/", "::1"),
        ("http://multicast.invalid/", "224.0.0.1"),
    ],
)
async def test_ssrf_rejects_every_non_global_destination(monkeypatch, url, resolved_ip):
    async def fake_getaddrinfo(*_args, **_kwargs):
        family = socket.AF_INET6 if ":" in resolved_ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (resolved_ip, 80))]

    monkeypatch.setattr("asyncio.get_running_loop", lambda: type("Loop", (), {"getaddrinfo": fake_getaddrinfo})())
    with pytest.raises(DownloadError):
        await _validate_public_destination(url)


@pytest.mark.no_db
def test_ssrf_rejects_dns_rebinding_peer():
    class FakeStream:
        def get_extra_info(self, name):
            assert name == "server_addr"
            return ("127.0.0.1", 80)

    class FakeResponse:
        extensions = {"network_stream": FakeStream()}

    with pytest.raises(DownloadError):
        _validate_connected_peer(FakeResponse(), {"8.8.8.8"})


class _FakeLimiter:
    async def acquire(self):
        return None


class _FakeStream:
    def __init__(self, peer="8.8.8.8"):
        self.peer = peer

    def get_extra_info(self, name):
        assert name == "server_addr"
        return (self.peer, 443)


class _FakeResponseContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_args):
        return None


class _FakeResponse:
    def __init__(self, *, headers, chunks=(), redirect=False):
        self.headers = headers
        self._chunks = chunks
        self.is_redirect = redirect
        self.extensions = {"network_stream": _FakeStream()}

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeClient:
    responses = []

    def __init__(self, **_kwargs):
        self._responses = iter(self.responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def stream(self, *_args):
        return _FakeResponseContext(next(self._responses))


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ssrf_revalidates_and_blocks_redirect_destination(monkeypatch, tmp_path):
    visited = []

    async def validate(url):
        visited.append(url)
        if url.startswith("http://127.0.0.1"):
            raise DownloadError("destino privado")
        return {"8.8.8.8"}

    _FakeClient.responses = [
        _FakeResponse(headers={"location": "http://127.0.0.1/admin"}, redirect=True)
    ]
    monkeypatch.setenv("PUBLIC_MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr("services.media.downloader._validate_public_destination", validate)
    monkeypatch.setattr("services.media.downloader.get_limiter", lambda: _FakeLimiter())
    monkeypatch.setattr("services.media.downloader.httpx.AsyncClient", _FakeClient)

    with pytest.raises(DownloadError, match="privado"):
        await download_product_image(1, "https://example.test/image.jpg")

    assert visited == [
        "https://example.test/image.jpg",
        "http://127.0.0.1/admin",
    ]


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,chunks,max_bytes",
    [
        ({"content-type": "text/html"}, [b"not-image"], 1024),
        ({"content-type": "image/jpeg"}, [b"1234"], 3),
    ],
)
async def test_download_rejects_mime_and_stream_size(
    monkeypatch, tmp_path, headers, chunks, max_bytes
):
    async def validate(_url):
        return {"8.8.8.8"}

    _FakeClient.responses = [_FakeResponse(headers=headers, chunks=chunks)]
    monkeypatch.setenv("PUBLIC_MEDIA_ROOT", str(tmp_path))
    monkeypatch.setenv("IMAGE_DOWNLOAD_MAX_BYTES", str(max_bytes))
    monkeypatch.setattr("services.media.downloader._validate_public_destination", validate)
    monkeypatch.setattr("services.media.downloader.get_limiter", lambda: _FakeLimiter())
    monkeypatch.setattr("services.media.downloader.httpx.AsyncClient", _FakeClient)

    with pytest.raises(DownloadError):
        await download_product_image(1, "https://example.test/image.jpg")
