# NG-HEADER: Nombre de archivo: drive_sync.py
# NG-HEADER: Ubicación: services/routers/drive_sync.py
# NG-HEADER: Descripción: Endpoints para sincronización de imágenes desde Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para sincronización de imágenes desde Google Drive con WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Set, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import DriveSyncItem, DriveSyncRun
from db.session import SessionLocal, get_session
from services.auth import SessionData, require_roles, require_csrf, require_websocket_roles
from services.jobs.drive_sync import sync_drive_images_task, PROGRESS_CHANNEL
from services.integrations.drive import GoogleDriveSync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/drive-sync", tags=["admin", "drive-sync"])

# Almacenar conexiones WebSocket activas
_active_connections: Set[WebSocket] = set()
_current_sync_id: Optional[str] = None
_sync_in_progress: bool = False
# Tareas de suscripción Redis activas (para limpieza)
_redis_subscriptions: Dict[str, asyncio.Task] = {}


class SyncStatusResponse(BaseModel):
    """Respuesta con estado de sincronización."""

    status: str
    message: str
    sync_id: Optional[str] = None


class RetryRunRequest(BaseModel):
    item_ids: list[int] | None = None


def _user_id(session: SessionData) -> int | None:
    if session.user:
        return session.user.id
    value = getattr(session, "user_id", None)
    return int(value) if value is not None else None


def _run_payload(run: DriveSyncRun, include_items: bool = False) -> dict:
    payload = {
        "id": run.id,
        "parent_run_id": run.parent_run_id,
        "source_folder_id": run.source_folder_id,
        "status": run.status,
        "total_items": run.total_items,
        "processed_items": run.processed_items,
        "success_count": run.success_count,
        "error_count": run.error_count,
        "skipped_count": run.skipped_count,
        "current_filename": run.current_filename,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
    if include_items:
        payload["items"] = [
            {
                "id": item.id,
                "position": item.position,
                "filename": item.filename,
                "sku": item.sku,
                "status": item.status,
                "error_message": item.error_message,
            }
            for item in run.items
        ]
    return payload


async def broadcast_progress(data: dict) -> None:
    """Envía progreso a todas las conexiones WebSocket activas."""
    if not _active_connections:
        logger.debug(f"No hay conexiones WebSocket activas para enviar progreso: {data.get('status')}")
        return

    message = json.dumps({
        "type": "drive_sync_progress",
        "event_id": uuid.uuid4().hex,
        "resource_id": data.get("sync_id") or data.get("resource_id"),
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    })

    logger.debug(f"Enviando progreso a {len(_active_connections)} conexiones: {data.get('status')} - {data.get('message', '')[:50]}")

    disconnected = set()
    for connection in _active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            logger.warning(f"Error enviando progreso a WebSocket: {e}")
            disconnected.add(connection)

    # Limpiar conexiones desconectadas
    for conn in disconnected:
        _active_connections.discard(conn)
        logger.info(f"Conexión WebSocket desconectada. Total restante: {len(_active_connections)}")


async def subscribe_to_progress(sync_id: str) -> None:
    """Se suscribe a Redis pub/sub para recibir progreso y reenviarlo vía WebSocket.
    
    Args:
        sync_id: ID de sincronización para filtrar mensajes.
    """
    global _sync_in_progress
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    try:
        # Intentar usar redis async (redis>=5.0)
        try:
            import redis.asyncio as aioredis
            redis_client = await aioredis.from_url(redis_url, decode_responses=False)
        except ImportError:
            # Fallback: redis síncrono no soporta async pub/sub bien
            # En este caso, usar polling periódico como alternativa
            logger.warning("redis.asyncio no disponible, usando polling como fallback")
            await _poll_redis_progress(sync_id, redis_url)
            return
        
        # Suscripción async
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(PROGRESS_CHANNEL)
        
        logger.info(f"Suscripción Redis iniciada para sync_id: {sync_id} en canal {PROGRESS_CHANNEL}")
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'].decode('utf-8'))
                        msg_sync_id = data.get('sync_id')
                        logger.debug(f"Mensaje Redis recibido: sync_id={msg_sync_id}, status={data.get('status')}")
                        
                        if msg_sync_id == sync_id:
                            logger.info(f"Procesando mensaje para sync_id {sync_id}: {data.get('status')}")
                            await _process_progress_message(data)
                            
                            # Si el estado es completed o error, terminar suscripción
                            if data.get('status') in ('completed', 'error', 'cancelled'):
                                logger.info(f"Sincronización {sync_id} finalizada con estado {data.get('status')}, cerrando suscripción")
                                global _current_sync_id
                                _sync_in_progress = False
                                _current_sync_id = None
                                break
                        else:
                            logger.debug(f"Ignorando mensaje de otro sync_id: {msg_sync_id} (esperado: {sync_id})")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error decodificando mensaje Redis: {e}, raw: {message.get('data', b'')[:100]}")
                    except Exception as e:
                        logger.error(f"Error procesando mensaje Redis: {e}", exc_info=True)
                elif message:
                    logger.debug(f"Mensaje Redis de tipo {message.get('type')}: {message}")
        finally:
            await pubsub.unsubscribe(PROGRESS_CHANNEL)
            await pubsub.close()
            await redis_client.aclose()
            logger.info(f"Suscripción Redis cerrada para sync_id: {sync_id}")
            
    except Exception as e:
        logger.error(f"Error en suscripción Redis: {e}", exc_info=True)
        _sync_in_progress = False


async def _poll_redis_progress(sync_id: str, redis_url: str) -> None:
    """Polling alternativo cuando redis.asyncio no está disponible.
    
    Args:
        sync_id: ID de sincronización.
        redis_url: URL de Redis.
    """
    global _sync_in_progress, _current_sync_id
    
    import redis
    
    def get_message_sync():
        """Obtiene mensaje de Redis de forma síncrona."""
        try:
            redis_client = redis.from_url(redis_url, decode_responses=False)
            pubsub = redis_client.pubsub()
            pubsub.subscribe(PROGRESS_CHANNEL)
            
            # Leer un mensaje con timeout
            message = pubsub.get_message(timeout=1.0)
            pubsub.close()
            redis_client.close()
            return message
        except Exception as e:
            logger.error(f"Error en polling Redis: {e}")
            return None
    
    logger.info(f"Polling Redis iniciado para sync_id: {sync_id}")
    
    try:
        while True:
            # Ejecutar get_message en thread separado para no bloquear
            message = await asyncio.to_thread(get_message_sync)
            
            if message and message.get('type') == 'message':
                try:
                    data = json.loads(message['data'].decode('utf-8'))
                    if data.get('sync_id') == sync_id:
                        await _process_progress_message(data)
                        
                        if data.get('status') in ('completed', 'error', 'cancelled'):
                            logger.info(f"Sincronización {sync_id} finalizada con estado: {data.get('status')}")
                            # Limpiar estado global
                            _sync_in_progress = False
                            _current_sync_id = None
                            break
                except Exception as e:
                    logger.error(f"Error procesando mensaje Redis: {e}")
            
            # Pequeña pausa para no saturar CPU
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        logger.info(f"Polling Redis cancelado para sync_id: {sync_id}")
        # Limpiar estado si se cancela
        if _current_sync_id == sync_id:
            _sync_in_progress = False
            _current_sync_id = None
    except Exception as e:
        logger.error(f"Error en polling Redis: {e}", exc_info=True)
        # Limpiar estado en caso de error
        if _current_sync_id == sync_id:
            _sync_in_progress = False
            _current_sync_id = None
    finally:
        logger.info(f"Polling Redis cerrado para sync_id: {sync_id}")


async def _process_progress_message(data: dict) -> None:
    """Procesa un mensaje de progreso recibido de Redis.
    
    Args:
        data: Datos de progreso (sin sync_id, ya filtrado).
    """
    progress_data = dict(data)
    await broadcast_progress(progress_data)


@router.post(
    "/start",
    dependencies=[Depends(require_csrf)],
    response_model=SyncStatusResponse,
)
async def start_drive_sync(
    source_folder_id: Optional[str] = Query(None, description="ID de carpeta de origen (opcional). Si no se proporciona, se usa DRIVE_SOURCE_FOLDER_ID del entorno. Permite procesar desde otras carpetas como 'Errores_SKU'."),
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
) -> SyncStatusResponse:
    """Inicia la sincronización de imágenes desde Google Drive.

    Requiere permisos de administrador.
    La sincronización se ejecuta en segundo plano y el progreso se reporta vía WebSocket.
    
    Args:
        source_folder_id: ID de carpeta de origen (opcional). Permite procesar desde
            otras carpetas como "Errores_SKU" en lugar de la carpeta principal.
    """
    global _sync_in_progress, _current_sync_id

    if _sync_in_progress:
        raise HTTPException(
            status_code=409,
            detail="Ya hay una sincronización en progreso",
        )

    sync_id = str(uuid.uuid4())
    _current_sync_id = sync_id
    _sync_in_progress = True
    db.add(
        DriveSyncRun(
            id=sync_id,
            source_folder_id=source_folder_id,
            status="queued",
            initiated_by_user_id=_user_id(session_data),
        )
    )
    await db.commit()

    # Encolar tarea en Dramatiq
    try:
        message = sync_drive_images_task.send(sync_id, source_folder_id=source_folder_id)
        logger.info(f"Sincronización Drive encolada (sync_id: {sync_id}, source_folder_id: {source_folder_id}, message_id: {message.message_id})")
    except Exception as e:
        _sync_in_progress = False
        _current_sync_id = None
        run = await db.get(DriveSyncRun, sync_id)
        if run:
            run.status = "failed"
            run.error_message = str(e)[:2000]
            run.completed_at = datetime.utcnow()
            await db.commit()
        logger.error(f"Error encolando sincronización Drive: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error al iniciar sincronización: {e}",
        )
    
    # Iniciar suscripción a Redis pub/sub en background
    subscription_task = asyncio.create_task(subscribe_to_progress(sync_id))
    _redis_subscriptions[sync_id] = subscription_task
    
    # Limpiar tarea cuando termine
    def cleanup_subscription():
        """Limpia la suscripción cuando termine."""
        if sync_id in _redis_subscriptions:
            task = _redis_subscriptions.pop(sync_id)
            if not task.done():
                task.cancel()
    
    subscription_task.add_done_callback(lambda _: cleanup_subscription())

    return SyncStatusResponse(
        status="started",
        message="Sincronización iniciada",
        sync_id=sync_id,
    )


@router.get(
    "/errors-folder-id",
    dependencies=[Depends(require_roles("admin"))],
)
async def get_errors_folder_id() -> dict:
    """Obtiene el ID de la carpeta 'Errores_SKU' para procesar archivos desde ahí.
    
    Returns:
        Dict con 'folder_id' si se encuentra, o 'error' si hay un problema.
    """
    try:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise HTTPException(status_code=500, detail="GOOGLE_APPLICATION_CREDENTIALS no está definido")
        
        source_folder_id = os.getenv("DRIVE_SOURCE_FOLDER_ID")
        if not source_folder_id:
            raise HTTPException(status_code=500, detail="DRIVE_SOURCE_FOLDER_ID no está definido")
        
        errors_folder_name = os.getenv("DRIVE_ERRORS_FOLDER_NAME", "Errores_SKU")
        
        # Resolver ruta de credenciales
        from pathlib import Path
        creds_path = Path(credentials_path)
        if not creds_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            creds_path = project_root / creds_path
        
        # Inicializar cliente y buscar carpeta
        drive_sync = GoogleDriveSync(str(creds_path), source_folder_id)
        await drive_sync.authenticate()
        
        errors_folder_id = await drive_sync.find_or_create_folder(source_folder_id, errors_folder_name)
        
        return {"folder_id": errors_folder_id, "folder_name": errors_folder_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo ID de carpeta Errores_SKU: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error obteniendo ID de carpeta: {e}")


@router.get(
    "/status",
    dependencies=[Depends(require_roles("admin"))],
    response_model=SyncStatusResponse,
)
async def get_sync_status(db: AsyncSession = Depends(get_session)) -> SyncStatusResponse:
    """Obtiene el estado actual de la sincronización."""
    active = await db.scalar(
        select(DriveSyncRun)
        .where(DriveSyncRun.status.in_(["queued", "running", "cancel_requested"]))
        .order_by(desc(DriveSyncRun.created_at))
        .limit(1)
    )
    if active:
        return SyncStatusResponse(
            status=active.status,
            message="Sincronización en progreso",
            sync_id=active.id,
        )
    return SyncStatusResponse(
        status="idle",
        message="No hay sincronización en progreso",
        sync_id=None,
    )


@router.get("/runs", dependencies=[Depends(require_roles("admin"))])
async def list_sync_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    filters = [DriveSyncRun.status == status] if status else []
    total = await db.scalar(select(func.count()).select_from(DriveSyncRun).where(*filters)) or 0
    result = await db.scalars(
        select(DriveSyncRun)
        .where(*filters)
        .order_by(desc(DriveSyncRun.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"items": [_run_payload(run) for run in result], "total": total, "page": page, "page_size": page_size}


@router.get("/runs/{run_id}", dependencies=[Depends(require_roles("admin"))])
async def get_sync_run(run_id: str, db: AsyncSession = Depends(get_session)) -> dict:
    result = await db.execute(
        select(DriveSyncRun).where(DriveSyncRun.id == run_id).options(selectinload(DriveSyncRun.items))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return _run_payload(run, include_items=True)


@router.post(
    "/runs/{run_id}/cancel",
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)],
)
async def cancel_sync_run(run_id: str, db: AsyncSession = Depends(get_session)) -> dict:
    run = await db.get(DriveSyncRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if run.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="La ejecución ya no puede cancelarse")
    run.status = "cancel_requested"
    run.cancel_requested_at = datetime.utcnow()
    await db.commit()
    return {"id": run.id, "status": run.status}


@router.post(
    "/runs/{run_id}/retry",
    dependencies=[Depends(require_csrf)],
)
async def retry_sync_run(
    run_id: str,
    payload: RetryRunRequest,
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    parent = await db.get(DriveSyncRun, run_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    query = select(DriveSyncItem).where(
        DriveSyncItem.run_id == run_id,
        DriveSyncItem.status.in_(["failed", "skipped"]),
    )
    if payload.item_ids:
        query = query.where(DriveSyncItem.id.in_(payload.item_ids))
    items = list(await db.scalars(query))
    if not items:
        raise HTTPException(status_code=409, detail="No hay elementos fallidos seleccionados")
    folder = await get_errors_folder_id()
    child_id = uuid.uuid4().hex
    child = DriveSyncRun(
        id=child_id,
        parent_run_id=run_id,
        source_folder_id=folder["folder_id"],
        status="queued",
        initiated_by_user_id=_user_id(session_data),
        total_items=len(items),
    )
    db.add(child)
    await db.commit()
    sync_drive_images_task.send(child_id, source_folder_id=folder["folder_id"], include_filenames=[item.filename for item in items])
    subscription_task = asyncio.create_task(subscribe_to_progress(child_id))
    _redis_subscriptions[child_id] = subscription_task
    return {"id": child_id, "parent_run_id": run_id, "status": "queued", "items": len(items)}


@router.websocket("/ws")
async def websocket_sync_status(websocket: WebSocket):
    """WebSocket para recibir actualizaciones de progreso en tiempo real.

    El cliente debe conectarse a este endpoint para recibir:
    - Estado de la sincronización (initializing, processing, completed, error)
    - Progreso actual (current/total)
    - SKU siendo procesado
    - Mensajes de estado
    """
    async with SessionLocal() as db:
        try:
            await require_websocket_roles(websocket, db, "admin")
        except HTTPException:
            return
    await websocket.accept()
    _active_connections.add(websocket)
    logger.info(f"Cliente conectado al WebSocket de sincronización. Total conexiones: {len(_active_connections)}")

    try:
        # Enviar estado inicial
        initial_status = {
            "type": "drive_sync_status",
            "status": "running" if _sync_in_progress else "idle",
            "sync_id": _current_sync_id,
        }
        await websocket.send_json(initial_status)
        logger.debug(f"Estado inicial enviado: {initial_status}")

        # Mantener conexión abierta y escuchar mensajes
        while True:
            try:
                # Esperar mensajes del cliente (pueden ser pings)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg.get("type") == "pong":
                        # Respuesta a nuestro ping, no hacer nada
                        pass
                except json.JSONDecodeError:
                    logger.warning(f"Mensaje WebSocket no válido: {data}")
            except asyncio.TimeoutError:
                # Enviar ping para mantener conexión
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception as e:
                    logger.warning(f"Error enviando ping: {e}")
                    break
    except WebSocketDisconnect:
        logger.info("Cliente desconectado del WebSocket de sincronización")
    except Exception as e:
        logger.error(f"Error en WebSocket de sincronización: {e}", exc_info=True)
    finally:
        _active_connections.discard(websocket)
        logger.info(f"Cliente desconectado. Total conexiones: {len(_active_connections)}")
        try:
            await websocket.close()
        except Exception:
            pass

