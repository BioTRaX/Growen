#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_validation_handler.py
# NG-HEADER: Ubicación: tests/test_validation_handler.py
# NG-HEADER: Descripción: Prueba del handler de validación (422) sanitizando bytes a str
# NG-HEADER: Lineamientos: Ver AGENTS.md

import asyncio
import json
import types
import pytest
from starlette.requests import Request
from fastapi.exceptions import RequestValidationError

# Importamos el handler real
from services.api import request_validation_error_handler


@pytest.mark.asyncio
async def test_request_validation_error_handler_sanitizes_bytes() -> None:
    # Construimos un Request mínimo
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/dummy",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope)

    # Forzamos un error de validación con bytes en el mensaje
    errs = [
        {"loc": ("body",), "msg": b"mensaje-en-bytes", "type": "custom"}
    ]
    exc = RequestValidationError(errs)

    resp = await request_validation_error_handler(request, exc)
    assert resp.status_code == 422

    # Verificamos que el cuerpo sea JSON serializable y contenga el str del mensaje
    payload = json.loads(resp.body.decode("utf-8"))
    assert "detail" in payload
    assert isinstance(payload["detail"], list)
    # Al menos uno de los mensajes debe contener la versión string del mensaje original
    msgs = [str(item.get("msg")) for item in payload["detail"]]
    assert any("mensaje-en-bytes" in m for m in msgs)
