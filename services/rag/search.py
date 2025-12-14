# NG-HEADER: Nombre de archivo: search.py
# NG-HEADER: Ubicación: services/rag/search.py
# NG-HEADER: Descripción: Servicio de búsqueda semántica en Knowledge Base (RAG)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de búsqueda RAG en la base de conocimientos."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.embeddings import get_embedding_service
from db.models import KnowledgeChunk, KnowledgeSource

logger = logging.getLogger(__name__)


class RAGSearchService:
    """Servicio para búsqueda semántica en Knowledge Base."""

    def __init__(self):
        self.embedding_service = get_embedding_service()

    async def search(
        self,
        query: str,
        session: AsyncSession,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Busca chunks relevantes en la base de conocimientos.
        
        Args:
            query: Texto de búsqueda del usuario
            session: Sesión de base de datos
            top_k: Número máximo de resultados
            min_similarity: Umbral mínimo de similitud (0-1)
            
        Returns:
            Lista de dicts con:
                - content: Texto del chunk
                - source: Nombre del archivo fuente
                - similarity: Score de similitud (0-1)
                - chunk_index: Índice del chunk en el documento
        """
        if not query or not query.strip():
            return []
        
        try:
            # Generar embedding de la consulta
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Búsqueda por similitud coseno usando pgvector
            # El operador <=> calcula distancia coseno (menor = más similar)
            # Convertimos a similitud: 1 - distancia
            from sqlalchemy import func, cast, text
            from pgvector.sqlalchemy import Vector
            
            # Convertir query_embedding a formato vector para pgvector
            query_vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            query_vector_expr = cast(query_vector_str, Vector(1536))
            
            # Usar operador <=> (cosine distance) de pgvector
            # La distancia coseno va de 0 (idénticos) a 2 (opuestos)
            # Similitud = 1 - distancia (va de -1 a 1, pero normalizamos a 0-1)
            distance_expr = KnowledgeChunk.embedding.op("<=>")(query_vector_expr)
            similarity_expr = (1 - func.cast(distance_expr, type_=func.float)).label("similarity")
            
            stmt = (
                select(
                    KnowledgeChunk,
                    KnowledgeSource.filename,
                    similarity_expr
                )
                .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
                .where(KnowledgeChunk.embedding.isnot(None))
                .order_by(distance_expr)  # Ordenar por distancia (menor = más similar)
                .limit(top_k * 2)  # Obtener más para filtrar por min_similarity
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            # Filtrar por similitud mínima y limitar
            results = []
            for chunk, filename, similarity in rows:
                if similarity >= min_similarity:
                    results.append({
                        "content": chunk.content,
                        "source": filename,
                        "similarity": float(similarity),
                        "chunk_index": chunk.chunk_index,
                        "source_id": chunk.source_id,
                    })
                    if len(results) >= top_k:
                        break
            
            logger.info(
                f"RAG search: query='{query[:50]}...', found={len(results)} chunks "
                f"(min_similarity={min_similarity})"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error en búsqueda RAG: {e}")
            return []

    async def search_and_format_context(
        self,
        query: str,
        session: AsyncSession,
        top_k: int = 3,
        min_similarity: float = 0.5,
    ) -> str:
        """
        Busca y formatea chunks como contexto para el LLM.
        
        Args:
            query: Texto de búsqueda
            session: Sesión de base de datos
            top_k: Número de chunks
            min_similarity: Umbral mínimo
            
        Returns:
            String formateado con contexto o string vacío si no hay resultados
        """
        chunks = await self.search(query, session, top_k, min_similarity)
        
        if not chunks:
            return ""
        
        # Formatear como contexto estructurado
        context_parts = []
        for idx, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"--- Fragmento {idx} (Fuente: {chunk['source']}) ---\n"
                f"{chunk['content']}\n"
            )
        
        return "\n".join(context_parts)


# Singleton
_rag_search_service: Optional[RAGSearchService] = None


def get_rag_search_service() -> RAGSearchService:
    """Obtener instancia singleton del servicio de búsqueda RAG."""
    global _rag_search_service
    
    if _rag_search_service is None:
        _rag_search_service = RAGSearchService()
    
    return _rag_search_service

