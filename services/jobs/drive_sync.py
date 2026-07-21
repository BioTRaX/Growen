# NG-HEADER: Nombre de archivo: drive_sync.py
# NG-HEADER: Ubicación: services/jobs/drive_sync.py
# NG-HEADER: Descripción: Jobs Dramatiq para sincronización de imágenes desde Google Drive.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Jobs Dramatiq para sincronización de Google Drive con progreso vía Redis Pub/Sub."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# FIX: Windows ProactorEventLoop no soporta psycopg async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    import dramatiq  # type: ignore
    _dramatiq_available = True
except Exception:
    _dramatiq_available = False
    def _noop_decorator(*dargs, **dkwargs):
        def _wrap(func):
            return func
        return _wrap
    class _StubModule:  # type: ignore
        actor = staticmethod(_noop_decorator)
    dramatiq = _StubModule()  # type: ignore

from workers.drive_sync import sync_drive_images
from db.models import DriveSyncItem, DriveSyncRun
from db.session import SessionLocal
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Canal Redis para progreso
PROGRESS_CHANNEL = "drive_sync:progress"


class DriveSyncCancelled(RuntimeError):
    """Señal cooperativa para detener una ejecución entre archivos."""


async def persist_progress(sync_id: str, data: dict) -> None:
    """Persiste el último estado antes de publicarlo como evento efímero."""

    async with SessionLocal() as session:
        run = await session.get(DriveSyncRun, sync_id)
        if not run:
            logger.warning("No existe drive_sync_run para sync_id=%s", sync_id)
            return
        if run.status == "cancel_requested":
            raise DriveSyncCancelled("Cancelación solicitada")

        now = datetime.utcnow()
        status = data.get("status")
        stats = data.get("stats") or {}
        if status in {"initializing", "listing", "processing"}:
            run.status = "running"
            run.started_at = run.started_at or now
        elif status == "completed":
            run.status = "partial" if int(stats.get("errors", 0)) else "completed"
            run.completed_at = now
        elif status == "error":
            run.status = "failed"
            run.error_message = str(data.get("error") or data.get("message") or "Error")[:2000]
            run.completed_at = now

        run.total_items = int(data.get("total") or run.total_items or 0)
        run.processed_items = int(data.get("current") or run.processed_items or 0)
        run.success_count = int(stats.get("processed") or 0)
        run.error_count = int(stats.get("errors") or 0)
        run.skipped_count = int(stats.get("no_sku") or 0)
        run.current_filename = str(data.get("filename") or "")[:500] or None

        listed_items = data.get("items") or []
        if listed_items:
            existing_names = set(await session.scalars(select(DriveSyncItem.filename).where(DriveSyncItem.run_id == sync_id)))
            for position, listed in enumerate(listed_items, start=1):
                filename_value = str(listed.get("filename") or "")[:500]
                if filename_value and filename_value not in existing_names:
                    session.add(DriveSyncItem(
                        run_id=sync_id,
                        position=position,
                        source_file_id=str(listed.get("source_file_id") or "")[:256] or None,
                        filename=filename_value,
                        status="pending",
                    ))

        filename = str(data.get("filename") or "").strip()
        if filename:
            item = await session.scalar(
                select(DriveSyncItem).where(DriveSyncItem.run_id == sync_id, DriveSyncItem.filename == filename)
            )
            if not item:
                item = DriveSyncItem(
                    run_id=sync_id,
                    position=max(1, int(data.get("current") or 1)),
                    filename=filename[:500],
                    sku=(str(data.get("sku"))[:120] if data.get("sku") else None),
                    status="processing",
                    started_at=now,
                )
                session.add(item)
            error = str(data.get("error") or "").strip()
            message = str(data.get("message") or "")
            if error:
                item.status = "failed"
                item.error_message = error[:2000]
                item.completed_at = now
            elif "sin formato SKU" in message or "SKU no canónico" in message:
                item.status = "skipped"
                item.completed_at = now
            elif "procesado exitosamente" in message:
                item.status = "processed"
                item.completed_at = now
        await session.commit()


async def publish_progress(sync_id: str, data: dict) -> None:
    """Publica progreso a Redis pub/sub.
    
    Args:
        sync_id: ID único de sincronización.
        data: Datos de progreso a publicar.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        # Intentar usar redis async (redis>=5.0)
        try:
            import redis.asyncio as aioredis
            redis_client = await aioredis.from_url(redis_url, decode_responses=False)
            message_payload = {
                "sync_id": sync_id,
                **data
            }
            message = json.dumps(message_payload).encode('utf-8')
            subscribers = await redis_client.publish(PROGRESS_CHANNEL, message)
            logger.debug(f"Progreso publicado a Redis: sync_id={sync_id}, status={data.get('status')}, subscribers={subscribers}")
            await redis_client.aclose()
        except ImportError:
            # Fallback a redis síncrono (versiones antiguas)
            import redis
            redis_client = redis.from_url(redis_url, decode_responses=False)
            message_payload = {
                "sync_id": sync_id,
                **data
            }
            message = json.dumps(message_payload).encode('utf-8')
            subscribers = redis_client.publish(PROGRESS_CHANNEL, message)
            logger.debug(f"Progreso publicado a Redis (sync): sync_id={sync_id}, status={data.get('status')}, subscribers={subscribers}")
            redis_client.close()
    except Exception as e:
        logger.error(f"Error publicando progreso a Redis: {e}", exc_info=True)


def create_progress_callback(sync_id: str):
    """Crea callback que publica progreso a Redis.
    
    Args:
        sync_id: ID único de sincronización.
        
    Returns:
        Función callback async que puede usarse con sync_drive_images.
    """
    async def callback(data: dict) -> None:
        """Callback que publica progreso a Redis pub/sub."""
        await persist_progress(sync_id, data)
        await publish_progress(sync_id, data)
    
    return callback


@dramatiq.actor(queue_name="drive_sync", max_retries=1, time_limit=3600000)  # 1 hora timeout
def sync_drive_images_task(
    sync_id: str,
    source_folder_id: str | None = None,
    include_filenames: list[str] | None = None,
) -> None:
    """Tarea Dramatiq para sincronización de imágenes desde Google Drive.
    
    Args:
        sync_id: ID único de sincronización (para tracking y filtrado de mensajes).
        source_folder_id: ID de carpeta de origen (opcional). Si no se proporciona,
            se usa DRIVE_SOURCE_FOLDER_ID del entorno.
    """
    logger.info(f"[DRAMATIQ] Tarea drive_sync recibida (sync_id: {sync_id}, source_folder_id: {source_folder_id})")
    
    async def run():
        """Ejecuta la sincronización con callback Redis."""
        try:
            logger.info(f"[DRAMATIQ] Iniciando sincronización Drive (sync_id: {sync_id}, source_folder_id: {source_folder_id})")
            # Publicar mensaje inicial para verificar que Redis pub/sub funciona
            await publish_progress(sync_id, {
                "status": "initializing",
                "current": 0,
                "total": 0,
                "message": "Iniciando sincronización...",
                "stats": {"processed": 0, "errors": 0, "no_sku": 0},
            })
            
            callback = create_progress_callback(sync_id)
            result = await sync_drive_images(
                progress_callback=callback,
                source_folder_id=source_folder_id,
                include_filenames=include_filenames,
            )
            logger.info(
                f"[DRAMATIQ] Sincronización completada (sync_id: {sync_id}): "
                f"{result.get('processed', 0)} procesados, "
                f"{result.get('errors', 0)} errores, "
                f"{result.get('no_sku', 0)} sin SKU"
            )
        except DriveSyncCancelled:
            async with SessionLocal() as session:
                run = await session.get(DriveSyncRun, sync_id)
                if run:
                    run.status = "cancelled"
                    run.completed_at = datetime.utcnow()
                    pending = list(await session.scalars(select(DriveSyncItem).where(DriveSyncItem.run_id == sync_id, DriveSyncItem.status.in_(["pending", "processing"]))))
                    for item in pending:
                        item.status = "cancelled"
                        item.completed_at = datetime.utcnow()
                    await session.commit()
            await publish_progress(sync_id, {
                "status": "cancelled",
                "current": 0,
                "total": 0,
                "message": "Sincronización cancelada por un administrador",
            })
        except Exception as e:
            logger.error(f"[DRAMATIQ] Error en sincronización Drive (sync_id: {sync_id}): {e}", exc_info=True)
            # Persistir y publicar error final.
            try:
                error_event = {
                    "status": "error",
                    "current": 0,
                    "total": 0,
                    "message": f"Error en sincronización: {e}",
                    "error": str(e),
                    "stats": {
                        "processed": 0,
                        "errors": 1,
                        "no_sku": 0,
                    },
                }
                await persist_progress(sync_id, error_event)
                await publish_progress(sync_id, error_event)
            except Exception as pub_err:
                logger.error(f"[DRAMATIQ] Error publicando error final: {pub_err}")
            raise
    
    asyncio.run(run())

