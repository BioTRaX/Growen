# NG-HEADER: Nombre de archivo: embeddings.py
# NG-HEADER: Ubicación: ai/embeddings.py
# NG-HEADER: Descripción: Embeddings locales Ollama de dimensión validada para RAG.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio asíncrono de embeddings con Ollama como proveedor canónico."""
from __future__ import annotations

import os
from typing import Any

import httpx


class EmbeddingUnavailableError(RuntimeError):
    """El proveedor local no puede producir un vector válido."""


class EmbeddingService:
    DEFAULT_MODEL = "qwen3-embedding:4b"
    EMBEDDING_DIMENSIONS = 1536

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.provider = os.getenv("RAG_EMBEDDING_PROVIDER", "ollama").strip().lower()
        if self.provider != "ollama":
            raise ValueError("rag_embedding_provider_not_allowed")
        self.base_url = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("RAG_EMBEDDING_MODEL", self.DEFAULT_MODEL)
        self.dimensions = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", str(self.EMBEDDING_DIMENSIONS)))
        if self.dimensions != self.EMBEDDING_DIMENSIONS:
            raise ValueError("rag_embedding_dimensions_must_be_1536")
        self.timeout = float(os.getenv("RAG_EMBEDDING_TIMEOUT", "120"))
        self._client = client

    def _validate(self, embedding: Any) -> list[float]:
        if not isinstance(embedding, list) or len(embedding) != self.EMBEDDING_DIMENSIONS:
            raise EmbeddingUnavailableError("ollama_embedding_dimension_invalid")
        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise EmbeddingUnavailableError("ollama_embedding_payload_invalid") from exc

    async def generate_embedding(self, text: str, model: str | None = None) -> list[float]:
        embeddings = await self.generate_embeddings_batch([text], model=model, batch_size=1)
        return embeddings[0]

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size debe ser mayor que cero")
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Texto en índice {index} está vacío")

        selected_model = model or self.model
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        output: list[list[float]] = []
        try:
            for start in range(0, len(texts), batch_size):
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": selected_model,
                        "input": texts[start:start + batch_size],
                        "dimensions": self.EMBEDDING_DIMENSIONS,
                        "truncate": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                batch = payload.get("embeddings")
                if not isinstance(batch, list) or len(batch) != len(texts[start:start + batch_size]):
                    raise EmbeddingUnavailableError("ollama_embedding_count_invalid")
                output.extend(self._validate(item) for item in batch)
            return output
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            if isinstance(exc, (ValueError, EmbeddingUnavailableError)):
                raise
            raise EmbeddingUnavailableError("ollama_embedding_unavailable") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def health(self) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=min(self.timeout, 10))
        try:
            response = await client.post(f"{self.base_url}/api/show", json={"model": self.model})
            response.raise_for_status()
            return {
                "status": "ok",
                "provider": self.provider,
                "model": self.model,
                "dimensions": self.EMBEDDING_DIMENSIONS,
            }
        except (httpx.HTTPError, ValueError, TypeError):
            return {
                "status": "unavailable",
                "provider": self.provider,
                "model": self.model,
                "dimensions": self.EMBEDDING_DIMENSIONS,
                "code": "ollama_embedding_unavailable",
            }
        finally:
            if owns_client:
                await client.aclose()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def generate_embedding(text: str) -> list[float]:
    return await get_embedding_service().generate_embedding(text)
