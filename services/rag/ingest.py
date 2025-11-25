# NG-HEADER: Nombre de archivo: ingest.py
# NG-HEADER: Ubicación: services/rag/ingest.py
# NG-HEADER: Descripción: Lógica de ingesta de documentos y generación de embeddings para RAG (Etapa 2)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Ingesta de documentos para RAG: chunking y vectorización."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ai.embeddings import EmbeddingService
from db.models import KnowledgeSource, KnowledgeChunk

logger = logging.getLogger(__name__)


class DocumentIngestor:
    """Servicio para ingestar documentos y generar embeddings."""
    
    # Configuración de chunking
    DEFAULT_CHUNK_SIZE = 1000  # caracteres
    DEFAULT_CHUNK_OVERLAP = 200  # caracteres de overlap entre chunks
    
    def __init__(self, embedding_service: EmbeddingService | None = None):
        """
        Inicializar ingestor de documentos.
        
        Args:
            embedding_service: Servicio de embeddings. Si no se provee, se crea uno nuevo.
        """
        from ai.embeddings import get_embedding_service
        self.embedding_service = embedding_service or get_embedding_service()
        
        # Configurar splitter de texto
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.DEFAULT_CHUNK_SIZE,
            chunk_overlap=self.DEFAULT_CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
            separators=[
                "\n\n",  # Párrafos
                "\n",    # Líneas
                ". ",    # Oraciones
                " ",     # Palabras
                "",      # Caracteres
            ]
        )
    
    def _calculate_hash(self, content: str) -> str:
        """
        Calcular hash SHA256 del contenido.
        
        Args:
            content: Contenido del documento
            
        Returns:
            Hash SHA256 en hexadecimal
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def _get_or_create_source(
        self, 
        session: AsyncSession,
        filename: str,
        content: str,
        meta_json: Dict[str, Any] | None = None
    ) -> KnowledgeSource:
        """
        Obtener o crear fuente de conocimiento.
        
        Si ya existe una fuente con el mismo filename y hash, se reutiliza.
        Si existe pero el hash cambió, se elimina la anterior y se crea nueva.
        
        Args:
            session: Sesión de base de datos
            filename: Nombre del archivo
            content: Contenido del documento
            meta_json: Metadatos adicionales
            
        Returns:
            Instancia de KnowledgeSource
        """
        content_hash = self._calculate_hash(content)
        
        # Buscar fuente existente
        stmt = select(KnowledgeSource).where(KnowledgeSource.filename == filename)
        result = await session.execute(stmt)
        existing_source = result.scalar_one_or_none()
        
        if existing_source:
            if existing_source.hash == content_hash:
                logger.info(f"Documento '{filename}' ya existe con mismo contenido (hash: {content_hash[:8]}...)")
                return existing_source
            else:
                logger.info(
                    f"Documento '{filename}' cambió. Eliminando versión anterior "
                    f"(hash: {existing_source.hash[:8]}... -> {content_hash[:8]}...)"
                )
                # El CASCADE en la FK eliminará automáticamente los chunks
                await session.delete(existing_source)
                await session.flush()
        
        # Crear nueva fuente
        source = KnowledgeSource(
            filename=filename,
            hash=content_hash,
            created_at=datetime.utcnow(),
            meta_json=meta_json or {}
        )
        session.add(source)
        await session.flush()  # Para obtener el ID
        
        logger.info(f"Creada fuente de conocimiento: '{filename}' (ID: {source.id}, hash: {content_hash[:8]}...)")
        return source
    
    async def ingest_document(
        self,
        filename: str,
        content: str,
        session: AsyncSession,
        meta_json: Dict[str, Any] | None = None,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Ingestar un documento: dividir en chunks y generar embeddings.
        
        Args:
            filename: Nombre del archivo
            content: Contenido del documento
            session: Sesión de base de datos async
            meta_json: Metadatos adicionales para el documento
            force_reindex: Si True, fuerza reindexación incluso si el hash es igual
            
        Returns:
            Dict con estadísticas de la ingesta:
                - source_id: ID de la fuente creada
                - chunks_created: Número de chunks creados
                - total_tokens_estimated: Estimación de tokens (aproximada)
                
        Raises:
            ValueError: Si el contenido está vacío
            Exception: Si falla la generación de embeddings
        """
        if not content or not content.strip():
            raise ValueError(f"El contenido del documento '{filename}' está vacío")
        
        logger.info(f"Iniciando ingesta de '{filename}' ({len(content)} caracteres)")
        
        # Obtener o crear fuente
        source = await self._get_or_create_source(
            session, 
            filename, 
            content, 
            meta_json
        )
        
        # Si ya existe y no forzamos reindexación, retornar
        if not force_reindex:
            stmt = select(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id)
            result = await session.execute(stmt)
            existing_chunks = result.scalars().all()
            
            if existing_chunks:
                logger.info(
                    f"Documento '{filename}' ya tiene {len(existing_chunks)} chunks indexados. "
                    "Usar force_reindex=True para reindexar."
                )
                return {
                    "source_id": source.id,
                    "chunks_created": 0,
                    "chunks_existing": len(existing_chunks),
                    "total_tokens_estimated": sum(len(c.content) // 4 for c in existing_chunks)
                }
        
        # Dividir texto en chunks
        text_chunks = self.text_splitter.split_text(content)
        logger.info(f"Documento dividido en {len(text_chunks)} chunks")
        
        if not text_chunks:
            logger.warning(f"No se generaron chunks para '{filename}'")
            return {
                "source_id": source.id,
                "chunks_created": 0,
                "total_tokens_estimated": 0
            }
        
        # Generar embeddings en batch (más eficiente)
        logger.info(f"Generando embeddings para {len(text_chunks)} chunks...")
        try:
            embeddings = await self.embedding_service.generate_embeddings_batch(text_chunks)
        except Exception as e:
            logger.error(f"Error generando embeddings para '{filename}': {str(e)}")
            raise Exception(f"Fallo al generar embeddings: {str(e)}") from e
        
        # Guardar chunks con embeddings
        chunks_created = 0
        total_tokens = 0
        
        for idx, (text, embedding) in enumerate(zip(text_chunks, embeddings)):
            chunk = KnowledgeChunk(
                source_id=source.id,
                chunk_index=idx,
                content=text,
                embedding=embedding,
                chunk_metadata={"length": len(text)}
            )
            session.add(chunk)
            chunks_created += 1
            total_tokens += len(text) // 4  # Estimación aproximada: 4 chars = 1 token
        
        await session.flush()
        
        logger.info(
            f"✅ Ingesta completada: '{filename}' -> {chunks_created} chunks "
            f"(~{total_tokens} tokens estimados)"
        )
        
        return {
            "source_id": source.id,
            "chunks_created": chunks_created,
            "total_tokens_estimated": total_tokens
        }
    
    async def ingest_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        session: AsyncSession,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Ingestar múltiples documentos.
        
        Args:
            documents: Lista de dicts con keys: 'filename', 'content', 'meta_json' (opcional)
            session: Sesión de base de datos async
            force_reindex: Si True, fuerza reindexación
            
        Returns:
            Dict con estadísticas agregadas:
                - total_documents: Total de documentos procesados
                - total_chunks: Total de chunks creados
                - failed_documents: Lista de filenames que fallaron
        """
        total_chunks = 0
        failed_documents = []
        
        for doc in documents:
            filename = doc.get("filename")
            content = doc.get("content")
            meta_json = doc.get("meta_json")
            
            if not filename or not content:
                logger.warning(f"Documento inválido (sin filename o content): {doc}")
                failed_documents.append(filename or "unknown")
                continue
            
            try:
                result = await self.ingest_document(
                    filename=filename,
                    content=content,
                    session=session,
                    meta_json=meta_json,
                    force_reindex=force_reindex
                )
                total_chunks += result["chunks_created"]
            except Exception as e:
                logger.error(f"Error procesando '{filename}': {str(e)}")
                failed_documents.append(filename)
        
        return {
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "failed_documents": failed_documents,
            "success_count": len(documents) - len(failed_documents)
        }
