# NG-HEADER: Nombre de archivo: embeddings.py
# NG-HEADER: Ubicación: ai/embeddings.py
# NG-HEADER: Descripción: Servicio de generación de embeddings usando OpenAI para RAG (Etapa 2)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de generación de embeddings para RAG."""
from __future__ import annotations

import asyncio
from typing import List

from openai import AsyncOpenAI

from agent_core.config import settings


class EmbeddingService:
    """Servicio para generar embeddings de texto usando OpenAI."""
    
    # Modelo recomendado: rápido, barato y dimensiones compatibles con nuestro schema (1536)
    DEFAULT_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    
    def __init__(self, api_key: str | None = None):
        """
        Inicializar servicio de embeddings.
        
        Args:
            api_key: API key de OpenAI. Si no se provee, se usa settings.openai_api_key
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY no configurada. "
                "Configurar en .env o pasar como parámetro."
            )
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def generate_embedding(self, text: str, model: str | None = None) -> List[float]:
        """
        Generar embedding para un texto.
        
        Args:
            text: Texto para generar embedding
            model: Modelo a usar (default: text-embedding-3-small)
            
        Returns:
            Lista de floats representando el vector embedding (1536 dimensiones)
            
        Raises:
            ValueError: Si el texto está vacío
            Exception: Si falla la llamada a OpenAI API
        """
        if not text or not text.strip():
            raise ValueError("El texto no puede estar vacío")
        
        model = model or self.DEFAULT_MODEL
        
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model
            )
            
            embedding = response.data[0].embedding
            
            # Validar dimensiones
            if len(embedding) != self.EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding tiene {len(embedding)} dimensiones, "
                    f"esperadas {self.EMBEDDING_DIMENSIONS}"
                )
            
            return embedding
            
        except Exception as e:
            raise Exception(f"Error generando embedding: {str(e)}") from e
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str], 
        model: str | None = None,
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generar embeddings para múltiples textos en batch.
        
        OpenAI permite hasta 2048 textos por request, pero usamos batches más pequeños
        para mejor manejo de errores.
        
        Args:
            texts: Lista de textos para generar embeddings
            model: Modelo a usar (default: text-embedding-3-small)
            batch_size: Tamaño de cada batch (default: 100)
            
        Returns:
            Lista de embeddings en el mismo orden que los textos
            
        Raises:
            ValueError: Si hay textos vacíos
            Exception: Si falla la llamada a OpenAI API
        """
        if not texts:
            return []
        
        # Validar textos
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Texto en índice {i} está vacío")
        
        model = model or self.DEFAULT_MODEL
        all_embeddings: List[List[float]] = []
        
        # Procesar en batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    input=batch,
                    model=model
                )
                
                # Los embeddings vienen en el mismo orden que los inputs
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                raise Exception(
                    f"Error generando embeddings para batch {i//batch_size + 1}: {str(e)}"
                ) from e
        
        return all_embeddings
    
    async def close(self):
        """Cerrar cliente (para limpieza de recursos)."""
        await self.client.close()


# Singleton global para reutilización
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """
    Obtener instancia singleton del servicio de embeddings.
    
    Returns:
        Instancia de EmbeddingService
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def generate_embedding(text: str) -> List[float]:
    """
    Función de conveniencia para generar un embedding.
    
    Args:
        text: Texto para generar embedding
        
    Returns:
        Vector embedding (1536 dimensiones)
    """
    service = get_embedding_service()
    return await service.generate_embedding(text)
