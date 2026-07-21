# NG-HEADER: Nombre de archivo: knowledge.py
# NG-HEADER: Ubicación: services/routers/knowledge.py
# NG-HEADER: Descripción: Endpoints de administración de Knowledge Base (RAG)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Admin endpoints para gestión de Knowledge Base (Cerebro)."""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import KnowledgeIndexTask
from db.session import get_session
from db.session import SessionLocal
from services.auth import SessionData, require_csrf, require_roles
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


MAX_UPLOAD_BYTES = int(os.getenv("KNOWLEDGE_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
SUPPORTED_MIME_TYPES = {"text/plain", "text/markdown", "application/pdf", "application/octet-stream"}


def _user_id(session: SessionData) -> int | None:
    if session.user:
        return session.user.id
    value = getattr(session, "user_id", None)
    return int(value) if value is not None else None


async def _create_task(
    db: AsyncSession,
    task_type: str,
    target: str,
    requested_by_user_id: int | None,
) -> str:
    """Crear una nueva tarea y retornar su ID."""
    task_id = uuid.uuid4().hex[:12]
    db.add(KnowledgeIndexTask(
        id=task_id,
        task_type=task_type,
        target=target,
        status="pending",
        requested_by_user_id=requested_by_user_id,
    ))
    await db.commit()
    return task_id


def _task_payload(task: KnowledgeIndexTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "type": task.task_type,
        "target": task.target,
        "status": task.status,
        "progress": task.progress,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "result": task.result,
        "error": task.error_message,
    }


async def _update_task(task_id: str, status: str, result: Any = None, error: str | None = None):
    """Actualizar estado de una tarea."""
    async with SessionLocal() as db:
        task = await db.get(KnowledgeIndexTask, task_id)
        if not task:
            return
        task.status = status
        task.result = result
        task.error_message = error
        if status == "running":
            task.started_at = task.started_at or datetime.utcnow()
            task.progress = max(task.progress, 1)
        if status in ("completed", "failed"):
            task.completed_at = datetime.utcnow()
            task.progress = 100
        await db.commit()


# --- Tareas en background ---

async def _run_index_file(task_id: str, filepath: str, force_reindex: bool):
    """Ejecutar indexación de archivo en background."""
    from db.session import SessionLocal
    
    await _update_task(task_id, "running")
    
    try:
        service = get_knowledge_service()
        async with SessionLocal() as session:
            result = await service.index_file(
                filepath=filepath,
                session=session,
                force_reindex=force_reindex
            )
            
            if result["success"]:
                await _update_task(task_id, "completed", result=result)
            else:
                await _update_task(task_id, "failed", error=result.get("error"))
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en tarea de indexación {task_id}: {e}")
        await _update_task(task_id, "failed", error=str(e))


async def _run_index_folder(task_id: str, force_reindex: bool):
    """Ejecutar indexación de carpeta en background."""
    from db.session import SessionLocal
    
    await _update_task(task_id, "running")
    
    try:
        service = get_knowledge_service()
        async with SessionLocal() as session:
            result = await service.index_directory(
                session=session,
                force_reindex=force_reindex
            )
            await _update_task(task_id, "completed", result=result)
            
    except Exception as e:
        logger.error(f"Error en tarea de indexación de carpeta {task_id}: {e}")
        await _update_task(task_id, "failed", error=str(e))


# --- Endpoints ---

@router.get("/files", dependencies=[Depends(require_roles("admin"))])
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
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)]
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
    if file.content_type and file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"MIME no soportado: {file.content_type}")
    
    service = get_knowledge_service()
    
    # Sanitizar nombre de archivo
    safe_filename = Path(file.filename).name  # Solo el nombre, sin path
    safe_filename = safe_filename.replace("..", "").replace("/", "_").replace("\\", "_")
    
    dest_path = service.knowledge_path / safe_filename
    
    # Verificar si ya existe
    overwrite = dest_path.exists()
    
    try:
        # Guardar archivo
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo permitido")
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo archivo {safe_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar archivo: {str(e)}")


@router.post(
    "/index",
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)]
)
async def index_knowledge(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
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
        task_id = await _create_task(db, "index_folder", "folder", _user_id(session_data))
        background_tasks.add_task(
            _run_index_folder,
            task_id,
            request.force_reindex
        )
        message = "Indexación de carpeta iniciada"
    else:
        # Validar que el archivo exista
        service = get_knowledge_service()
        root = service.knowledge_path.resolve()
        file_path = (root / request.target).resolve()
        if not file_path.is_relative_to(root):
            raise HTTPException(status_code=400, detail="Ruta de conocimiento inválida")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {request.target}")
        
        task_id = await _create_task(db, "index_file", request.target, _user_id(session_data))
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


@router.get("/tasks/{task_id}", dependencies=[Depends(require_roles("admin"))])
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """
    Obtener estado de una tarea de indexación.
    """
    task = await db.get(KnowledgeIndexTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Tarea no encontrada: {task_id}")
    return _task_payload(task)


@router.get("/tasks", dependencies=[Depends(require_roles("admin"))])
async def list_tasks(limit: int = 20, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """
    Listar tareas recientes de indexación.
    """
    # Ordenar por fecha de inicio descendente
    tasks = list(await db.scalars(
        select(KnowledgeIndexTask).order_by(desc(KnowledgeIndexTask.created_at)).limit(min(max(limit, 1), 100))
    ))
    
    return {
        "tasks": [_task_payload(task) for task in tasks],
        "total": len(tasks),
    }


@router.get("/sources", dependencies=[Depends(require_roles("admin"))])
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
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)]
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


@router.get("/status", dependencies=[Depends(require_roles("admin"))])
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
    running_tasks = list(await db.scalars(
        select(KnowledgeIndexTask)
        .where(KnowledgeIndexTask.status == "running")
        .order_by(desc(KnowledgeIndexTask.created_at))
    ))
    status["tasks_running"] = len(running_tasks)
    status["current_task"] = _task_payload(running_tasks[0]) if running_tasks else None
    
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
    root = service.knowledge_path.resolve()
    file_path = (root / filename).resolve()
    if not file_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Ruta de conocimiento inválida")
    
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

