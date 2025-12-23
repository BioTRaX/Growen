# NG-HEADER: Nombre de archivo: rag.py
# NG-HEADER: Ubicación: services/routers/rag.py
# NG-HEADER: Descripción: Endpoints API públicos para búsqueda RAG (Retrieval-Augmented Generation)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""API endpoints para búsqueda semántica en Knowledge Base."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from services.rag.search import get_rag_search_service

logger = logging.getLogger(__name__)


# --- Modelos Pydantic ---

class RAGSearchRequest(BaseModel):
    """Request para búsqueda semántica en Knowledge Base."""
    query: str = Field(..., min_length=1, max_length=2000, description="Texto de búsqueda")
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de resultados a retornar"
    )
    min_similarity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Umbral mínimo de similitud (0-1)"
    )


class RAGSearchResult(BaseModel):
    """Un resultado individual de búsqueda RAG."""
    content: str = Field(..., description="Contenido del fragmento de texto")
    source: str = Field(..., description="Nombre del archivo fuente")
    similarity: float = Field(..., description="Score de similitud (0-1)")
    chunk_index: int = Field(..., description="Índice del fragmento en el documento")
    source_id: int = Field(..., description="ID de la fuente en la DB")


class RAGSearchResponse(BaseModel):
    """Respuesta de búsqueda RAG."""
    query: str = Field(..., description="Query original")
    results: List[RAGSearchResult] = Field(
        default_factory=list,
        description="Lista de resultados ordenados por similitud"
    )
    total_results: int = Field(..., description="Número total de resultados encontrados")


# --- Router ---

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.post("/search", response_model=RAGSearchResponse)
async def search_knowledge(
    request: RAGSearchRequest,
    session: AsyncSession = Depends(get_session),
) -> RAGSearchResponse:
    """
    Búsqueda semántica en la base de conocimientos.
    
    Utiliza embeddings de OpenAI y pgvector para encontrar fragmentos de texto
    relevantes basados en similitud coseno.
    
    **Parámetros:**
    - **query**: Texto de búsqueda (1-2000 caracteres)
    - **top_k**: Número máximo de resultados (1-20, default: 5)
    - **min_similarity**: Umbral mínimo de similitud (0-1, default: 0.5)
    
    **Retorna:**
    - Lista de fragmentos relevantes con contenido, fuente y score de similitud
    
    **Ejemplo de uso:**
    ```json
    {
        "query": "¿Cuál es el horario de atención?",
        "top_k": 3,
        "min_similarity": 0.6
    }
    ```
    """
    try:
        search_service = get_rag_search_service()
        
        results = await search_service.search(
            query=request.query,
            session=session,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        
        return RAGSearchResponse(
            query=request.query,
            results=[
                RAGSearchResult(**result)
                for result in results
            ],
            total_results=len(results),
        )
        
    except ValueError as e:
        logger.warning(f"Búsqueda RAG inválida: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en búsqueda RAG: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno al procesar la búsqueda"
        )


@router.get("/health")
async def rag_health() -> dict[str, Any]:
    """
    Health check del servicio RAG.
    
    Verifica que el servicio de embeddings esté configurado correctamente.
    """
    try:
        from ai.embeddings import get_embedding_service
        service = get_embedding_service()
        return {
            "status": "ok",
            "embedding_model": service.DEFAULT_MODEL,
            "embedding_dimensions": service.EMBEDDING_DIMENSIONS,
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
        }
