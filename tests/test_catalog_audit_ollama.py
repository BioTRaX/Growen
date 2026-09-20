#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_catalog_audit_ollama.py
# NG-HEADER: Ubicación: tests/test_catalog_audit_ollama.py
# NG-HEADER: Descripción: Contrato estricto del modelo local del auditor de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import httpx
import pytest

from services.catalog_audit.ollama_client import CatalogAuditOllamaClient, SemanticAuditError


@pytest.mark.asyncio
async def test_ollama_usa_parametros_deterministas_y_schema_json() -> None:
    observed: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"response": '{"classification":"container","score":98,"fields":[],"critical":false}'})

    client = CatalogAuditOllamaClient(transport=httpx.MockTransport(handler))
    result = await client.audit({"name": "Maceta 20L", "content": {}})

    assert result["classification"] == "container"
    assert observed["model"] == "llama3.1:8b"
    assert observed["options"] == {"temperature": 0, "num_ctx": 4096, "num_predict": 2048}
    assert isinstance(observed["format"], dict)


@pytest.mark.asyncio
async def test_ollama_falla_cerrado_con_json_invalido() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"response": "no-json"}))

    with pytest.raises(SemanticAuditError, match="invalid_json"):
        await CatalogAuditOllamaClient(transport=transport).audit({"name": "Producto", "content": {}})


@pytest.mark.asyncio
async def test_ollama_reintenta_una_vez_si_la_primera_respuesta_no_es_json() -> None:
    responses = iter([
        httpx.Response(200, json={"response": "no-json"}),
        httpx.Response(200, json={"response": '{"classification":"liquid","score":91,"fields":[],"critical":false}'}),
    ])
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return next(responses)

    result = await CatalogAuditOllamaClient(transport=httpx.MockTransport(handler)).audit(
        {"name": "Fertilizante", "content": {}}
    )

    assert result["classification"] == "liquid"
    assert attempts == 2
