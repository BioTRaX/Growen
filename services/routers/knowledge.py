# NG-HEADER: Nombre de archivo: knowledge.py
# NG-HEADER: Ubicación: services/routers/knowledge.py
# NG-HEADER: Descripción: Endpoints de administración de Knowledge Base (RAG)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Admin endpoints para gestión de Knowledge Base (Cerebro)."""
from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from services.auth import require_csrf, require_roles
from services.rag.service import SUPPORTED_EXTENSIONS, KnowledgeService, get_knowledge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/knowledge", tags=["admin", "knowledge"])


# --- Modelos Pydantic ---

class IndexRequest(BaseModel):
    """Request para indexación."""
    target: str  # "filename.md" para archivo específico, "folder" para carpeta completa
    force_reindex: bool = False


class IndexResponse(BaseModel):
    """Respuesta de indexación."""
    task_id: str
    status: str
    message: str


# --- Estado de tareas en memoria (simple) ---
# En producción considerar Redis o DB para persistencia
_tasks: Dict[str, Dict[str, Any]] = {}


def _create_task(task_type: str, target: str) -> str:
    """Crear una nueva tarea y retornar su ID."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "id": task_id,
        "type": task_type,
        "target": target,
        "status": "pending",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }
    return task_id


def _update_task(task_id: str, status: str, result: Any = None, error: str | None = None):
    """Actualizar estado de una tarea."""
    if task_id in _tasks:
        _tasks[task_id]["status"] = status
        _tasks[task_id]["result"] = result
        _tasks[task_id]["error"] = error
        if status in ("completed", "failed"):
            _tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()


# --- Tareas en background ---

async def _run_index_file(task_id: str, filepath: str, force_reindex: bool):
    """Ejecutar indexación de archivo en background."""
    from db.session import SessionLocal
    
    _update_task(task_id, "running")
    
    try:
        service = get_knowledge_service()
        async with SessionLocal() as session:
            result = await service.index_file(
                filepath=filepath,
                session=session,
                force_reindex=force_reindex
            )
            
            if result["success"]:
                _update_task(task_id, "completed", result=result)
            else:
                _update_task(task_id, "failed", error=result.get("error"))
                
    except Exception as e:
        logger.error(f"Error en tarea de indexación {task_id}: {e}")
        _update_task(task_id, "failed", error=str(e))


async def _run_index_folder(task_id: str, force_reindex: bool):
    """Ejecutar indexación de carpeta en background."""
    from db.session import SessionLocal
    
    _update_task(task_id, "running")
    
    try:
        service = get_knowledge_service()
        async with SessionLocal() as session:
            result = await service.index_directory(
                session=session,
                force_reindex=force_reindex
            )
            _update_task(task_id, "completed", result=result)
            
    except Exception as e:
        logger.error(f"Error en tarea de indexación de carpeta {task_id}: {e}")
        _update_task(task_id, "failed", error=str(e))


# --- Endpoints ---

@router.get("/files", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def list_files(
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Lista archivos en la carpeta /Conocimientos con estado de indexación.
    
    Retorna:
        - files: Lista de archivos con nombre, tamaño, extensión, estado indexado
        - total: Número total de archivos
    """
    service = get_knowledge_service()
    files = await service.list_files_with_status(db)
    
    return {
        "files": files,
        "total": len(files),
        "supported_extensions": list(SUPPORTED_EXTENSIONS),
    }


@router.post(
    "/upload",
    dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)]
)
async def upload_file(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Sube un archivo a la carpeta /Conocimientos.
    
    Formatos soportados: MD, TXT, PDF
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido")
    
    # Validar extensión
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no soportada: {ext}. Soportadas: {list(SUPPORTED_EXTENSIONS)}"
        )
    
    service = get_knowledge_service()
    
    # Sanitizar nombre de archivo
    safe_filename = Path(file.filename).name  # Solo el nombre, sin path
    safe_filename = safe_filename.replace("..", "").replace("/", "_").replace("\\", "_")
    
    dest_path = service.knowledge_path / safe_filename
    
    # Verificar si ya existe
    overwrite = dest_path.exists()
    
    try:
        # Guardar archivo
        content = await file.read()
        
        with open(dest_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Archivo subido: {safe_filename} ({len(content)} bytes)")
        
        return {
            "success": True,
            "filename": safe_filename,
            "size_bytes": len(content),
            "overwritten": overwrite,
            "message": f"Archivo {'actualizado' if overwrite else 'subido'} correctamente",
        }
        
    except Exception as e:
        logger.error(f"Error subiendo archivo {safe_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar archivo: {str(e)}")


@router.post(
    "/index",
    dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)]
)
async def index_knowledge(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
) -> IndexResponse:
    """
    Dispara indexación de conocimientos.
    
    Body:
        - target: "filename.md" para archivo específico, "folder" para carpeta completa
        - force_reindex: Si true, reindexar aunque el contenido no haya cambiado
    
    Retorna:
        - task_id: ID de la tarea para consultar estado
        - status: Estado inicial (pending)
    """
    if request.target == "folder":
        task_id = _create_task("index_folder", "folder")
        background_tasks.add_task(
            _run_index_folder,
            task_id,
            request.force_reindex
        )
        message = "Indexación de carpeta iniciada"
    else:
        # Validar que el archivo exista
        service = get_knowledge_service()
        file_path = service.knowledge_path / request.target
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {request.target}")
        
        task_id = _create_task("index_file", request.target)
        background_tasks.add_task(
            _run_index_file,
            task_id,
            request.target,
            request.force_reindex
        )
        message = f"Indexación de '{request.target}' iniciada"
    
    return IndexResponse(
        task_id=task_id,
        status="pending",
        message=message
    )


@router.get("/tasks/{task_id}", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Obtener estado de una tarea de indexación.
    """
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Tarea no encontrada: {task_id}")
    
    return _tasks[task_id]


@router.get("/tasks", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def list_tasks(limit: int = 20) -> Dict[str, Any]:
    """
    Listar tareas recientes de indexación.
    """
    # Ordenar por fecha de inicio descendente
    sorted_tasks = sorted(
        _tasks.values(),
        key=lambda t: t["started_at"],
        reverse=True
    )[:limit]
    
    return {
        "tasks": sorted_tasks,
        "total": len(_tasks),
    }


@router.get("/sources", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def list_sources(
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Lista fuentes de conocimiento indexadas en la base de datos.
    """
    service = get_knowledge_service()
    sources = await service.get_sources(db)
    
    return {
        "sources": sources,
        "total": len(sources),
    }


@router.delete(
    "/sources/{source_id}",
    dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)]
)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Elimina una fuente de conocimiento de la base de datos.
    
    Nota: No elimina el archivo del disco, solo la indexación.
    """
    service = get_knowledge_service()
    result = await service.delete_source(source_id, db)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Fuente no encontrada"))
    
    return result


@router.get("/status", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def get_status(
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Obtener estadísticas generales del sistema de conocimientos.
    
    Retorna:
        - total_sources: Fuentes indexadas
        - total_chunks: Fragmentos de texto vectorizados
        - files_in_folder: Archivos en la carpeta
        - files_pending: Archivos sin indexar
        - last_indexed_at: Última indexación
    """
    service = get_knowledge_service()
    status = await service.get_index_status(db)
    
    # Agregar info de tareas en curso
    running_tasks = [t for t in _tasks.values() if t["status"] == "running"]
    status["tasks_running"] = len(running_tasks)
    status["current_task"] = running_tasks[0] if running_tasks else None
    
    return status


@router.delete(
    "/files/{filename:path}",
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)]
)
async def delete_file(
    filename: str,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Elimina un archivo de la carpeta /Conocimientos Y su indexación de la DB.
    
    Solo disponible para rol admin.
    """
    service = get_knowledge_service()
    file_path = service.knowledge_path / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {filename}")
    
    # Primero, buscar y eliminar la fuente de la DB si existe
    files_with_status = await service.list_files_with_status(db)
    source_deleted = False
    
    for f in files_with_status:
        if f["path"] == filename and f["source_id"]:
            result = await service.delete_source(f["source_id"], db)
            source_deleted = result["success"]
            break
    
    # Luego eliminar el archivo
    try:
        file_path.unlink()
        logger.info(f"Archivo eliminado: {filename}")
        
        return {
            "success": True,
            "filename": filename,
            "source_deleted": source_deleted,
            "message": f"Archivo eliminado{' (y su indexación)' if source_deleted else ''}",
        }
        
    except Exception as e:
        logger.error(f"Error eliminando archivo {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar archivo: {str(e)}")

