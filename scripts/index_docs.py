#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: index_docs.py
# NG-HEADER: Ubicación: scripts/index_docs.py
# NG-HEADER: Descripción: Script de carga inicial de documentos para RAG desde docs/knowledge_base/
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Script para indexar documentos de conocimiento en la base de datos RAG.

Escanea la carpeta docs/knowledge_base/ buscando archivos .md y .txt,
los procesa con chunking y genera embeddings usando OpenAI.

Uso:
    python scripts/index_docs.py [--force] [--path PATH]
    
    --force: Fuerza reindexación de documentos existentes
    --path:  Ruta alternativa a docs/knowledge_base/
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List

# Fix para Windows + psycopg async
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from services.rag.ingest import DocumentIngestor
from agent_core.config import settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scan_knowledge_directory(path: Path) -> List[dict]:
    """
    Escanear directorio de conocimiento y recopilar archivos.
    
    Args:
        path: Ruta al directorio de conocimiento
        
    Returns:
        Lista de dicts con 'filename', 'content', 'meta_json'
    """
    if not path.exists():
        logger.warning(f"Directorio no existe: {path}")
        return []
    
    documents = []
    extensions = ['.md', '.txt']
    
    for file_path in path.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            try:
                # Leer contenido
                content = file_path.read_text(encoding='utf-8')
                
                # Metadatos
                relative_path = file_path.relative_to(path)
                meta_json = {
                    "extension": file_path.suffix,
                    "size_bytes": file_path.stat().st_size,
                    "relative_path": str(relative_path),
                    "full_path": str(file_path)
                }
                
                documents.append({
                    "filename": str(relative_path),
                    "content": content,
                    "meta_json": meta_json
                })
                
                logger.info(f"✓ Encontrado: {relative_path} ({len(content)} caracteres)")
                
            except Exception as e:
                logger.error(f"Error leyendo {file_path}: {str(e)}")
    
    return documents


async def index_documents(
    knowledge_path: Path,
    force_reindex: bool = False
) -> None:
    """
    Indexar todos los documentos del directorio de conocimiento.
    
    Args:
        knowledge_path: Ruta al directorio docs/knowledge_base/
        force_reindex: Si True, fuerza reindexación de documentos existentes
    """
    logger.info("=" * 80)
    logger.info("INDEXACIÓN DE DOCUMENTOS RAG")
    logger.info("=" * 80)
    logger.info(f"Directorio: {knowledge_path.absolute()}")
    logger.info(f"Forzar reindexación: {force_reindex}")
    logger.info(f"OpenAI API Key configurada: {'✓' if settings.openai_api_key else '✗'}")
    logger.info("")
    
    if not settings.openai_api_key:
        logger.error("❌ Secreto OpenAI no configurado")
        logger.error("   Configurar OPENAI_API_KEY_FILE con una ruta absoluta fuera del repositorio")
        return
    
    # Escanear directorio
    logger.info("Escaneando directorio de conocimiento...")
    documents = await scan_knowledge_directory(knowledge_path)
    
    if not documents:
        logger.warning("⚠️  No se encontraron documentos para indexar")
        logger.info(f"   Agregar archivos .md o .txt en: {knowledge_path}")
        return
    
    logger.info(f"📚 Encontrados {len(documents)} documentos\n")
    
    # Crear ingestor
    ingestor = DocumentIngestor()
    
    # Procesar documentos
    async for session in get_session():
        try:
            result = await ingestor.ingest_documents_batch(
                documents=documents,
                session=session,
                force_reindex=force_reindex
            )
            
            # Commit transacción
            await session.commit()
            
            # Mostrar estadísticas
            logger.info("")
            logger.info("=" * 80)
            logger.info("RESUMEN DE INDEXACIÓN")
            logger.info("=" * 80)
            logger.info(f"Total documentos procesados: {result['total_documents']}")
            logger.info(f"Documentos exitosos: {result['success_count']}")
            logger.info(f"Documentos fallidos: {len(result['failed_documents'])}")
            logger.info(f"Total chunks creados: {result['total_chunks']}")
            
            if result['failed_documents']:
                logger.warning("\n⚠️  Documentos que fallaron:")
                for failed in result['failed_documents']:
                    logger.warning(f"   - {failed}")
            
            # Estimación de costo (aproximada)
            # text-embedding-3-small: $0.02 por 1M tokens
            total_tokens = sum(
                len(doc['content']) // 4  # Aproximación: 4 chars = 1 token
                for doc in documents
            )
            estimated_cost = (total_tokens / 1_000_000) * 0.02
            
            logger.info("")
            logger.info(f"Tokens estimados: ~{total_tokens:,}")
            logger.info(f"Costo estimado: ~${estimated_cost:.6f} USD")
            logger.info("=" * 80)
            
            if result['success_count'] > 0:
                logger.info("✅ Indexación completada exitosamente")
            else:
                logger.error("❌ Ningún documento se indexó correctamente")
                
        except Exception as e:
            logger.error(f"❌ Error durante la indexación: {str(e)}")
            await session.rollback()
            raise
        break  # Solo usar la primera sesión del generador


async def main():
    """Función principal del script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Indexar documentos de conocimiento para RAG"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar reindexación de documentos existentes"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("docs/knowledge_base"),
        help="Ruta al directorio de conocimiento (default: docs/knowledge_base)"
    )
    
    args = parser.parse_args()
    
    await index_documents(
        knowledge_path=args.path,
        force_reindex=args.force
    )


if __name__ == "__main__":
    asyncio.run(main())
