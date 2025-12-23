# NG-HEADER: Nombre de archivo: test_rag_search.py
# NG-HEADER: Ubicación: tests/test_rag_search.py
# NG-HEADER: Descripción: Tests unitarios para el endpoint de búsqueda RAG
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Tests para el endpoint /api/v1/rag/search."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Skip si no está disponible pgvector (entorno SQLite)
try:
    import pgvector  # noqa: F401
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector not available (SQLite test env)")
]


class TestRAGSearchEndpoint:
    """Tests para POST /api/v1/rag/search."""

    async def test_search_empty_query(self, client):
        """Query vacío debe retornar error 422."""
        resp = await client.post(
            "/api/v1/rag/search",
            json={"query": ""}
        )
        assert resp.status_code == 422

    async def test_search_query_too_long(self, client):
        """Query muy largo debe retornar error 422."""
        long_query = "a" * 2001
        resp = await client.post(
            "/api/v1/rag/search",
            json={"query": long_query}
        )
        assert resp.status_code == 422

    async def test_search_invalid_top_k(self, client):
        """top_k fuera de rango debe retornar error 422."""
        resp = await client.post(
            "/api/v1/rag/search",
            json={"query": "test", "top_k": 100}
        )
        assert resp.status_code == 422

    async def test_search_invalid_min_similarity(self, client):
        """min_similarity fuera de rango debe retornar error 422."""
        resp = await client.post(
            "/api/v1/rag/search",
            json={"query": "test", "min_similarity": 2.0}
        )
        assert resp.status_code == 422

    async def test_search_valid_request_no_results(self, client):
        """Búsqueda válida sin resultados debe retornar lista vacía."""
        mock_results = []
        
        with patch("services.routers.rag.get_rag_search_service") as mock_service:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_results)
            mock_service.return_value = mock_instance
            
            resp = await client.post(
                "/api/v1/rag/search",
                json={"query": "pregunta sin respuesta"}
            )
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "pregunta sin respuesta"
        assert data["results"] == []
        assert data["total_results"] == 0

    async def test_search_valid_request_with_results(self, client):
        """Búsqueda válida con resultados debe retornar estructura correcta."""
        mock_results = [
            {
                "content": "Este es el contenido del chunk",
                "source": "documento.md",
                "similarity": 0.85,
                "chunk_index": 0,
                "source_id": 1,
            },
            {
                "content": "Otro fragmento relevante",
                "source": "otro.md",
                "similarity": 0.72,
                "chunk_index": 2,
                "source_id": 2,
            },
        ]
        
        with patch("services.routers.rag.get_rag_search_service") as mock_service:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=mock_results)
            mock_service.return_value = mock_instance
            
            resp = await client.post(
                "/api/v1/rag/search",
                json={"query": "pregunta de prueba", "top_k": 3}
            )
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "pregunta de prueba"
        assert len(data["results"]) == 2
        assert data["total_results"] == 2
        
        # Verificar estructura del primer resultado
        first = data["results"][0]
        assert first["content"] == "Este es el contenido del chunk"
        assert first["source"] == "documento.md"
        assert first["similarity"] == 0.85
        assert first["chunk_index"] == 0
        assert first["source_id"] == 1

    async def test_search_default_parameters(self, client):
        """Búsqueda usa parámetros por defecto correctamente."""
        with patch("services.routers.rag.get_rag_search_service") as mock_service:
            mock_instance = AsyncMock()
            mock_instance.search = AsyncMock(return_value=[])
            mock_service.return_value = mock_instance
            
            resp = await client.post(
                "/api/v1/rag/search",
                json={"query": "test query"}
            )
            
            # Verificar que se llamó con parámetros por defecto
            call_kwargs = mock_instance.search.call_args.kwargs
            assert call_kwargs["top_k"] == 5
            assert call_kwargs["min_similarity"] == 0.5

        assert resp.status_code == 200


class TestRAGHealthEndpoint:
    """Tests para GET /api/v1/rag/health."""

    async def test_health_ok(self, client):
        """Health check retorna status ok cuando todo está configurado."""
        with patch("services.routers.rag.get_embedding_service") as mock_service:
            mock_instance = AsyncMock()
            mock_instance.DEFAULT_MODEL = "text-embedding-3-small"
            mock_instance.EMBEDDING_DIMENSIONS = 1536
            mock_service.return_value = mock_instance
            
            resp = await client.get("/api/v1/rag/health")
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["embedding_model"] == "text-embedding-3-small"
        assert data["embedding_dimensions"] == 1536

    async def test_health_error(self, client):
        """Health check retorna status error cuando hay problemas."""
        with patch("services.routers.rag.get_embedding_service") as mock_service:
            mock_service.side_effect = ValueError("OPENAI_API_KEY no configurada")
            
            resp = await client.get("/api/v1/rag/health")
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "OPENAI_API_KEY" in data["detail"]
