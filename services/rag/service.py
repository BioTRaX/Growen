# NG-HEADER: Nombre de archivo: service.py
# NG-HEADER: Ubicación: services/rag/service.py
# NG-HEADER: Descripción: Servicio de gestión de Knowledge Base (orquestador de indexación RAG)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de gestión de Knowledge Base para RAG."""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KnowledgeChunk, KnowledgeSource
from services.rag.ingest import DocumentIngestor
from services.rag.pdf_parser import PDFParseError, extract_text_from_pdf

logger = logging.getLogger(__name__)

# Extensiones de archivo soportadas
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}

# Ruta por defecto de la carpeta de conocimientos
DEFAULT_KNOWLEDGE_PATH = Path("Conocimientos")


class KnowledgeService:
    """Servicio para gestionar la base de conocimientos (Knowledge Base)."""

    def __init__(self, knowledge_path: Path | str | None = None):
        """
        Inicializar servicio de conocimientos.
        
        Args:
            knowledge_path: Ruta a la carpeta de conocimientos. 
                           Por defecto usa /Conocimientos o /app/Conocimientos en Docker.
        """
        if knowledge_path:
            self.knowledge_path = Path(knowledge_path)
        else:
            # Detectar si estamos en Docker o local
            if Path("/app/Conocimientos").exists():
                self.knowledge_path = Path("/app/Conocimientos")
            else:
                # Buscar relativo al proyecto
                self.knowledge_path = self._find_knowledge_path()
        
        self.ingestor = DocumentIngestor()
        logger.info(f"KnowledgeService inicializado con path: {self.knowledge_path}")

    def _find_knowledge_path(self) -> Path:
        """Encontrar la carpeta de conocimientos relativa al proyecto."""
        # Intentar varias ubicaciones comunes
        candidates = [
            DEFAULT_KNOWLEDGE_PATH,  # ./Conocimientos
            Path(__file__).parent.parent.parent / "Conocimientos",  # Desde services/rag/
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        
        # Si no existe, crear y retornar la ruta por defecto
        DEFAULT_KNOWLEDGE_PATH.mkdir(parents=True, exist_ok=True)
        return DEFAULT_KNOWLEDGE_PATH.resolve()

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash SHA256 de un archivo."""
        content = self._read_file_content(file_path)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _read_file_content(self, file_path: Path) -> str:
        """
        Leer contenido de un archivo según su extensión.
        
        Args:
            file_path: Ruta al archivo
            
        Returns:
            Contenido del archivo como texto
            
        Raises:
            ValueError: Si la extensión no es soportada
            PDFParseError: Si hay error al parsear PDF
        """
        ext = file_path.suffix.lower()
        
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Extensión no soportada: {ext}. Soportadas: {SUPPORTED_EXTENSIONS}")
        
        if ext == ".pdf":
            return extract_text_from_pdf(file_path)
        else:
            # MD y TXT se leen como texto plano
            return file_path.read_text(encoding="utf-8")

    def list_files(self, session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """
        Listar archivos en la carpeta de conocimientos.
        
        Nota: Este método es síncrono para el listado de archivos.
        Para verificar estado de indexación, usar list_files_with_status().
        
        Returns:
            Lista de dicts con información de cada archivo:
                - filename: Nombre del archivo
                - path: Ruta relativa
                - extension: Extensión del archivo
                - size_bytes: Tamaño en bytes
                - modified_at: Fecha de última modificación
        """
        if not self.knowledge_path.exists():
            logger.warning(f"Carpeta de conocimientos no existe: {self.knowledge_path}")
            return []
        
        files = []
        
        for file_path in self.knowledge_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            
            # Ignorar archivos ocultos y temporales
            if file_path.name.startswith(".") or file_path.name.startswith("~"):
                continue
            
            try:
                stat = file_path.stat()
                relative_path = file_path.relative_to(self.knowledge_path)
                
                files.append({
                    "filename": file_path.name,
                    "path": str(relative_path),
                    "full_path": str(file_path),
                    "extension": ext,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception as e:
                logger.warning(f"Error leyendo info de {file_path}: {e}")
                continue
        
        # Ordenar por nombre
        files.sort(key=lambda x: x["filename"].lower())
        return files

    async def list_files_with_status(
        self, 
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Listar archivos con estado de indexación.
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Lista de archivos con campos adicionales:
                - indexed: bool - Si está indexado en DB
                - source_id: int | None - ID de la fuente si está indexada
                - chunks_count: int - Número de chunks si está indexado
                - needs_reindex: bool - Si el hash cambió desde la última indexación
        """
        files = self.list_files()
        
        if not files:
            return files
        
        # Obtener todas las fuentes de la DB
        stmt = select(KnowledgeSource)
        result = await session.execute(stmt)
        sources = {s.filename: s for s in result.scalars().all()}
        
        # Obtener conteo de chunks por source_id
        stmt = select(
            KnowledgeChunk.source_id,
            func.count(KnowledgeChunk.id).label("chunks_count")
        ).group_by(KnowledgeChunk.source_id)
        result = await session.execute(stmt)
        chunks_counts = {row.source_id: row.chunks_count for row in result}
        
        # Enriquecer archivos con estado
        for file_info in files:
            filename = file_info["path"]  # Usar path relativo como key
            source = sources.get(filename)
            
            if source:
                # Calcular hash actual para detectar cambios
                try:
                    current_hash = self._calculate_file_hash(Path(file_info["full_path"]))
                    needs_reindex = source.hash != current_hash
                except Exception:
                    needs_reindex = True
                
                file_info.update({
                    "indexed": True,
                    "source_id": source.id,
                    "chunks_count": chunks_counts.get(source.id, 0),
                    "indexed_at": source.created_at.isoformat() if source.created_at else None,
                    "needs_reindex": needs_reindex,
                })
            else:
                file_info.update({
                    "indexed": False,
                    "source_id": None,
                    "chunks_count": 0,
                    "indexed_at": None,
                    "needs_reindex": False,
                })
        
        return files

    async def index_file(
        self,
        filepath: str,
        session: AsyncSession,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Indexar un solo archivo.
        
        Args:
            filepath: Ruta relativa al archivo dentro de /Conocimientos
            session: Sesión de base de datos
            force_reindex: Si True, fuerza reindexación aunque el hash no haya cambiado
            
        Returns:
            Dict con resultado de la indexación:
                - success: bool
                - filename: str
                - source_id: int | None
                - chunks_created: int
                - error: str | None
        """
        file_path = self.knowledge_path / filepath
        
        if not file_path.exists():
            return {
                "success": False,
                "filename": filepath,
                "source_id": None,
                "chunks_created": 0,
                "error": f"Archivo no encontrado: {filepath}",
            }
        
        try:
            # Leer contenido
            content = self._read_file_content(file_path)
            
            if not content or not content.strip():
                return {
                    "success": False,
                    "filename": filepath,
                    "source_id": None,
                    "chunks_created": 0,
                    "error": "El archivo está vacío o no contiene texto extraíble",
                }
            
            # Metadatos
            stat = file_path.stat()
            meta_json = {
                "extension": file_path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "source_path": str(file_path.relative_to(self.knowledge_path)),
            }
            
            # Ingestar documento
            result = await self.ingestor.ingest_document(
                filename=filepath,
                content=content,
                session=session,
                meta_json=meta_json,
                force_reindex=force_reindex
            )
            
            await session.commit()
            
            return {
                "success": True,
                "filename": filepath,
                "source_id": result["source_id"],
                "chunks_created": result["chunks_created"],
                "chunks_existing": result.get("chunks_existing", 0),
                "tokens_estimated": result["total_tokens_estimated"],
                "error": None,
            }
            
        except PDFParseError as e:
            logger.error(f"Error parseando PDF '{filepath}': {e}")
            return {
                "success": False,
                "filename": filepath,
                "source_id": None,
                "chunks_created": 0,
                "error": f"Error de PDF: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Error indexando '{filepath}': {e}")
            await session.rollback()
            return {
                "success": False,
                "filename": filepath,
                "source_id": None,
                "chunks_created": 0,
                "error": str(e),
            }

    async def index_directory(
        self,
        session: AsyncSession,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Indexar todos los archivos de la carpeta de conocimientos.
        
        Args:
            session: Sesión de base de datos
            force_reindex: Si True, fuerza reindexación de todos los archivos
            
        Returns:
            Dict con estadísticas:
                - total_files: int
                - success_count: int
                - failed_count: int
                - total_chunks: int
                - failed_files: List[str]
                - results: List[Dict] - Resultado de cada archivo
        """
        files = self.list_files()
        
        if not files:
            return {
                "total_files": 0,
                "success_count": 0,
                "failed_count": 0,
                "total_chunks": 0,
                "failed_files": [],
                "results": [],
            }
        
        results = []
        total_chunks = 0
        failed_files = []
        
        for file_info in files:
            result = await self.index_file(
                filepath=file_info["path"],
                session=session,
                force_reindex=force_reindex
            )
            results.append(result)
            
            if result["success"]:
                total_chunks += result.get("chunks_created", 0)
            else:
                failed_files.append(file_info["path"])
        
        return {
            "total_files": len(files),
            "success_count": len(files) - len(failed_files),
            "failed_count": len(failed_files),
            "total_chunks": total_chunks,
            "failed_files": failed_files,
            "results": results,
        }

    async def delete_source(
        self,
        source_id: int,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Eliminar una fuente de conocimiento de la DB (no del disco).
        
        Args:
            source_id: ID de la fuente a eliminar
            session: Sesión de base de datos
            
        Returns:
            Dict con resultado:
                - success: bool
                - filename: str | None
                - chunks_deleted: int
                - error: str | None
        """
        try:
            # Buscar la fuente
            stmt = select(KnowledgeSource).where(KnowledgeSource.id == source_id)
            result = await session.execute(stmt)
            source = result.scalar_one_or_none()
            
            if not source:
                return {
                    "success": False,
                    "filename": None,
                    "chunks_deleted": 0,
                    "error": f"Fuente no encontrada: ID {source_id}",
                }
            
            filename = source.filename
            
            # Contar chunks antes de eliminar
            stmt = select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.source_id == source_id
            )
            chunks_count = await session.scalar(stmt) or 0
            
            # Eliminar (CASCADE eliminará chunks automáticamente)
            await session.delete(source)
            await session.commit()
            
            logger.info(f"Eliminada fuente '{filename}' (ID: {source_id}) con {chunks_count} chunks")
            
            return {
                "success": True,
                "filename": filename,
                "chunks_deleted": chunks_count,
                "error": None,
            }
            
        except Exception as e:
            logger.error(f"Error eliminando fuente {source_id}: {e}")
            await session.rollback()
            return {
                "success": False,
                "filename": None,
                "chunks_deleted": 0,
                "error": str(e),
            }

    async def get_index_status(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Obtener estadísticas generales del índice de conocimientos.
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Dict con estadísticas:
                - total_sources: int
                - total_chunks: int
                - total_tokens_estimated: int
                - files_in_folder: int
                - files_pending: int (archivos no indexados)
                - last_indexed_at: str | None
                - sources: List[Dict] - Detalle de cada fuente
        """
        # Contar fuentes
        stmt = select(func.count(KnowledgeSource.id))
        total_sources = await session.scalar(stmt) or 0
        
        # Contar chunks
        stmt = select(func.count(KnowledgeChunk.id))
        total_chunks = await session.scalar(stmt) or 0
        
        # Estimar tokens (suma de longitud de contenido / 4)
        stmt = select(func.sum(func.length(KnowledgeChunk.content)))
        total_chars = await session.scalar(stmt) or 0
        total_tokens_estimated = total_chars // 4
        
        # Última indexación
        stmt = select(func.max(KnowledgeSource.created_at))
        last_indexed = await session.scalar(stmt)
        
        # Archivos en carpeta
        files = self.list_files()
        files_in_folder = len(files)
        
        # Archivos con estado
        files_with_status = await self.list_files_with_status(session)
        files_pending = sum(1 for f in files_with_status if not f["indexed"])
        files_need_reindex = sum(1 for f in files_with_status if f.get("needs_reindex", False))
        
        # Detalle de fuentes
        stmt = select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc())
        result = await session.execute(stmt)
        sources = result.scalars().all()
        
        # Chunks por fuente
        stmt = select(
            KnowledgeChunk.source_id,
            func.count(KnowledgeChunk.id).label("chunks_count")
        ).group_by(KnowledgeChunk.source_id)
        result = await session.execute(stmt)
        chunks_by_source = {row.source_id: row.chunks_count for row in result}
        
        sources_detail = [
            {
                "id": s.id,
                "filename": s.filename,
                "hash": s.hash[:12] + "..." if s.hash else None,
                "chunks_count": chunks_by_source.get(s.id, 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sources
        ]
        
        return {
            "total_sources": total_sources,
            "total_chunks": total_chunks,
            "total_tokens_estimated": total_tokens_estimated,
            "files_in_folder": files_in_folder,
            "files_pending": files_pending,
            "files_need_reindex": files_need_reindex,
            "last_indexed_at": last_indexed.isoformat() if last_indexed else None,
            "knowledge_path": str(self.knowledge_path),
            "sources": sources_detail,
        }

    async def get_sources(self, session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Obtener todas las fuentes indexadas.
        
        Args:
            session: Sesión de base de datos
            
        Returns:
            Lista de fuentes con sus metadatos
        """
        stmt = select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc())
        result = await session.execute(stmt)
        sources = result.scalars().all()
        
        # Chunks por fuente
        stmt = select(
            KnowledgeChunk.source_id,
            func.count(KnowledgeChunk.id).label("chunks_count")
        ).group_by(KnowledgeChunk.source_id)
        result = await session.execute(stmt)
        chunks_by_source = {row.source_id: row.chunks_count for row in result}
        
        return [
            {
                "id": s.id,
                "filename": s.filename,
                "hash": s.hash,
                "chunks_count": chunks_by_source.get(s.id, 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "meta_json": s.meta_json,
            }
            for s in sources
        ]


# Singleton para reutilización
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service(knowledge_path: Path | str | None = None) -> KnowledgeService:
    """
    Obtener instancia singleton del servicio de conocimientos.
    
    Args:
        knowledge_path: Ruta opcional a la carpeta de conocimientos
        
    Returns:
        Instancia de KnowledgeService
    """
    global _knowledge_service
    
    if _knowledge_service is None or knowledge_path is not None:
        _knowledge_service = KnowledgeService(knowledge_path)
    
    return _knowledge_service

