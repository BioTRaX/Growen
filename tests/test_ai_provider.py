# NG-HEADER: Nombre de archivo: test_ai_provider.py
# NG-HEADER: Ubicación: tests/test_ai_provider.py
# NG-HEADER: Descripción: Pruebas unitarias de la fábrica de proveedores IA.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import asyncio
import json
import logging

import httpx

from services.ai import provider


class DummyStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        yield "no-json"
        yield json.dumps({"response": "ok"})


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.HTTPError("fallo")

    def stream(self, *args, **kwargs):
        return DummyStream()


def test_ai_reply_logs_invalid_json(monkeypatch, caplog):
    monkeypatch.setattr("services.ai.provider.httpx.AsyncClient", DummyClient)
    with caplog.at_level(logging.WARNING):
        text = asyncio.get_event_loop().run_until_complete(provider.ai_reply("hola"))
    assert text == "ok"
    assert any(
        "Línea JSON inválida" in record.message for record in caplog.records
    )
