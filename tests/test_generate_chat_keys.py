#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_generate_chat_keys.py
# NG-HEADER: Ubicación: tests/test_generate_chat_keys.py
# NG-HEADER: Descripción: Pruebas de captura segura del canary Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import httpx
import pytest

from scripts.generate_chat_keys import _capture_canary_user_id


def _mock_client(monkeypatch, responses):
    client_type = httpx.Client
    transport = httpx.MockTransport(lambda request: responses.pop(0))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_type(transport=transport, **kwargs))


def test_capture_canary_uses_private_from_id(monkeypatch):
    responses = [
        httpx.Response(200, json={"ok": True, "result": {"url": ""}}),
        httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {"update_id": 1, "message": {"text": "/canary", "chat": {"type": "group"}, "from": {"id": 111}}},
                    {"update_id": 2, "message": {"text": "/start", "chat": {"type": "private"}, "from": {"id": 222}}},
                    {"update_id": 3, "message": {"text": "/canary", "chat": {"type": "private"}, "from": {"id": 333}}},
                ],
            },
        ),
    ]
    _mock_client(monkeypatch, responses)

    assert _capture_canary_user_id("123456:abcdefghijklmnopqrstuvwxyz", 5) == "333"


def test_capture_canary_rejects_active_webhook(monkeypatch):
    responses = [httpx.Response(200, json={"ok": True, "result": {"url": "https://example.invalid/hook"}})]
    _mock_client(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="telegram_webhook_active"):
        _capture_canary_user_id("123456:abcdefghijklmnopqrstuvwxyz", 5)
