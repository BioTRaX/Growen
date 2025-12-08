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

logger = logging.getLogger(__name__)

# Canal Redis para progreso
PROGRESS_CHANNEL = "drive_sync:progress"


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
        await publish_progress(sync_id, data)
    
    return callback


@dramatiq.actor(queue_name="drive_sync", max_retries=1, time_limit=3600000)  # 1 hora timeout
def sync_drive_images_task(sync_id: str, source_folder_id: str | None = None) -> None:
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
            result = await sync_drive_images(progress_callback=callback, source_folder_id=source_folder_id)
            logger.info(
                f"[DRAMATIQ] Sincronización completada (sync_id: {sync_id}): "
                f"{result.get('processed', 0)} procesados, "
                f"{result.get('errors', 0)} errores, "
                f"{result.get('no_sku', 0)} sin SKU"
            )
        except Exception as e:
            logger.error(f"[DRAMATIQ] Error en sincronización Drive (sync_id: {sync_id}): {e}", exc_info=True)
            # Publicar error final
            try:
                await publish_progress(sync_id, {
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
                })
            except Exception as pub_err:
                logger.error(f"[DRAMATIQ] Error publicando error final: {pub_err}")
            raise
    
    asyncio.run(run())

