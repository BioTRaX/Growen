#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_ollama_local.py
# NG-HEADER: Ubicación: tests/test_ollama_local.py
# NG-HEADER: Descripción: Contratos fail-closed de generación y embeddings Ollama.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import httpx
import pytest

from ai.embeddings import EmbeddingService, EmbeddingUnavailableError
from ai.providers.ollama_provider import OllamaProvider, OllamaUnavailableError


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ollama_generation_async_uses_local_api(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = __import__("json").loads(request.content)
        assert body["options"]["num_ctx"] == 4096
        return httpx.Response(200, json={"response": "respuesta local"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        assert await provider.generate_async("hola") == "respuesta local"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ollama_generation_fails_closed():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client=client)
        with pytest.raises(OllamaUnavailableError, match="http_error") as failure:
            await provider.generate_async("texto privado")
        assert failure.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_embeddings_request_1536_dimensions(monkeypatch):
    vector = [0.0] * 1536

    async def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["dimensions"] == 1536
        assert body["model"] == "qwen3-embedding:4b"
        return httpx.Response(200, json={"embeddings": [vector]})

    monkeypatch.setenv("RAG_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:4b")
    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "1536")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = EmbeddingService(client=client)
        assert len(await service.generate_embedding("consulta")) == 1536


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_embeddings_reject_wrong_dimension(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.0] * 10]})

    monkeypatch.setenv("RAG_EMBEDDING_DIMENSIONS", "1536")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = EmbeddingService(client=client)
        with pytest.raises(EmbeddingUnavailableError, match="dimension_invalid"):
            await service.generate_embedding("consulta")
