#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: telegram_polling.py
# NG-HEADER: Ubicación: workers/telegram_polling.py
# NG-HEADER: Descripción: Worker de Long Polling para Telegram Bot
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Worker de Long Polling para Telegram Bot.

Este worker permite usar el bot de Telegram sin necesidad de webhooks o URLs públicas.
Ideal para desarrollo local sin necesidad de ngrok o servidores expuestos.

Uso:
    python workers/telegram_polling.py

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN: Token del bot de Telegram
    TELEGRAM_ENABLED: 1 para habilitar (opcional, default: 0)
    DB_URL: URL de conexión a la base de datos (opcional, usa settings por defecto)
"""

from __future__ import annotations

import os
import sys
import logging
import asyncio
import re
from typing import Any, Dict, Optional

# FIX: Windows ProactorEventLoop no soporta psycopg async
# Debe ejecutarse ANTES de cualquier import que use asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    import httpx
except ImportError:
    print("ERROR: httpx no está instalado. Instalar con: pip install httpx")
    sys.exit(1)

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from agent_core.config import settings
from services.chat.telegram_handler import handle_telegram_message
from services.notifications.telegram import send_message as tg_send

# Resolver ROOT antes de configurar logging
ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class TokenMaskingFilter(logging.Filter):
    """Filtro que enmascara tokens de Telegram en los logs."""
    
    # Patrón para detectar tokens de Telegram en URLs: bot<ID>:<TOKEN>
    # Ejemplo: bot8483738256:AAEM18ir0qNRUQtHFAUp2t0MFiIlQX_Tcrk
    TELEGRAM_TOKEN_PATTERN = re.compile(
        r'(bot\d+):([A-Za-z0-9_-]+)',
        re.IGNORECASE
    )
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filtra y enmascara tokens en el mensaje de log."""
        if hasattr(record, 'msg') and record.msg:
            # Convertir mensaje a string si no lo es
            msg = str(record.msg)
            # Reemplazar tokens: bot<ID>:<TOKEN> -> bot<ID>:***MASKED***
            msg = self.TELEGRAM_TOKEN_PATTERN.sub(r'\1:***MASKED***', msg)
            record.msg = msg
            
            # También enmascarar en args si existen
            if hasattr(record, 'args') and record.args:
                args = list(record.args)
                for i, arg in enumerate(args):
                    if isinstance(arg, str):
                        args[i] = self.TELEGRAM_TOKEN_PATTERN.sub(r'\1:***MASKED***', arg)
                record.args = tuple(args)
        
        return True


# Configuración de logging
# Usar nivel INFO por defecto, pero permitir override con LOG_LEVEL
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_handlers = [logging.StreamHandler()]  # Siempre consola

# Intentar agregar handler de archivo, pero no fallar si hay error de permisos
try:
    log_file_path = LOGS_DIR / "worker_telegram_polling.log"
    # Usar modo 'a' (append) para evitar problemas si el archivo está abierto
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding="utf-8")
    log_handlers.append(file_handler)
except (PermissionError, OSError) as e:
    # Si no se puede escribir al archivo (está abierto o sin permisos), solo usar consola
    print(f"Warning: No se pudo abrir archivo de log {log_file_path}: {e}")
    print("Continuando solo con logging a consola...")

# Crear filtro de enmascaramiento de tokens
token_filter = TokenMaskingFilter()

# Aplicar filtro a todos los handlers
for handler in log_handlers:
    handler.addFilter(token_filter)

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Reducir verbosidad de httpx/httpcore (solo WARNING y superior)
# Esto evita que se logueen automáticamente las URLs con tokens
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Aplicar filtro también al root logger para capturar cualquier log que escape
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if not any(isinstance(f, TokenMaskingFilter) for f in handler.filters):
        handler.addFilter(token_filter)

# Configuración de base de datos - usar settings como en db/session.py
DB_URL = os.getenv("DB_URL") or settings.db_url
engine = create_async_engine(DB_URL, future=True, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "0").lower() in ("1", "true", "yes")

# Configuración de polling
POLLING_TIMEOUT = int(os.getenv("TELEGRAM_POLLING_TIMEOUT", "30"))  # segundos
POLLING_RETRY_DELAY = int(os.getenv("TELEGRAM_POLLING_RETRY_DELAY", "5"))  # segundos entre reintentos


async def delete_webhook(token: str) -> bool:
    """
    Elimina el webhook configurado en Telegram (obligatorio antes de usar polling).
    
    Args:
        token: Token del bot de Telegram
        
    Returns:
        True si se eliminó exitosamente, False en caso contrario
    """
    url = f"{TELEGRAM_API_BASE}/bot{token}/deleteWebhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"drop_pending_updates": True})
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                logger.info("✓ Webhook eliminado exitosamente")
                return True
            else:
                logger.warning(f"⚠ Error eliminando webhook: {result.get('description', 'Unknown')}")
                return False
    except Exception as e:
        logger.error(f"✗ Error al eliminar webhook: {e}")
        return False


async def get_updates(
    token: str,
    offset: Optional[int] = None,
    timeout: int = POLLING_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    """
    Obtiene actualizaciones de Telegram usando Long Polling.
    
    Args:
        token: Token del bot de Telegram
        offset: ID del último update procesado + 1 (None para obtener todos)
        timeout: Timeout en segundos para long polling (default: 30)
        
    Returns:
        Dict con la respuesta de getUpdates o None si hay error
    """
    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
    params: Dict[str, Any] = {
        "timeout": timeout,
        "allowed_updates": ["message"],  # Solo mensajes, ignorar otros tipos de updates
    }
    if offset is not None:
        params["offset"] = offset
    
    try:
        async with httpx.AsyncClient(timeout=timeout + 10) as client:  # Timeout mayor que polling
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            result = resp.json()
            # Log detallado si hay error en la respuesta de Telegram
            if not result.get("ok"):
                error_code = result.get("error_code")
                description = result.get("description", "Unknown error")
                logger.error(f"✗ Telegram API error: code={error_code}, description={description}")
            return result
    except httpx.TimeoutException:
        # Timeout es normal en long polling, no es un error
        logger.debug("Timeout en getUpdates (normal en long polling)")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"✗ HTTP error obteniendo updates: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"✗ Error obteniendo updates: {type(e).__name__}: {e}", exc_info=True)
        return None


async def process_message(text: str, chat_id: int, image_file_id: Optional[str] = None) -> None:
    """
    Procesa un mensaje de Telegram usando el handler compartido.
    
    Args:
        text: Texto del mensaje (puede estar vacío si solo hay imagen)
        chat_id: ID del chat de Telegram
        image_file_id: File ID de imagen de Telegram (opcional)
    """
    logger.info(f"🔄 Procesando mensaje de chat_id={chat_id}, text='{text[:50] if text else '(solo imagen)'}', has_image={bool(image_file_id)}")
    try:
        # Crear sesión de DB para este mensaje
        async with SessionLocal() as db:
            logger.debug(f"✓ Sesión de DB creada para chat_id={chat_id}")
            # Procesar mensaje usando el handler compartido
            answer = await handle_telegram_message(
                text=text,
                chat_id=str(chat_id),
                db=db,
                image_file_id=image_file_id,  # Pasar file_id si existe
            )
            logger.info(f"✓ Respuesta generada para chat_id={chat_id}: {answer[:100] if answer else '(vacía)'}...")
            
            # Enviar respuesta
            sent = await tg_send(answer, chat_id=str(chat_id))
            if sent:
                logger.info(f"✓ Mensaje enviado exitosamente a chat_id={chat_id}")
            else:
                logger.warning(f"⚠ No se pudo enviar mensaje a chat_id={chat_id} (tg_send retornó False)")
            
    except Exception as e:
        logger.error(f"✗ Error procesando mensaje de chat_id={chat_id}: {e}", exc_info=True)
        # Intentar enviar mensaje de error al usuario
        try:
            await tg_send(
                "Disculpá, hubo un error procesando tu mensaje. Probá más tarde.",
                chat_id=str(chat_id)
            )
        except Exception as send_err:
            logger.error(f"✗ Error al enviar mensaje de error: {send_err}", exc_info=True)


async def run_polling() -> None:
    """
    Ejecuta el bucle principal de Long Polling.
    
    Obtiene actualizaciones de Telegram, procesa mensajes y mantiene el offset
    para evitar procesar mensajes duplicados.
    """
    if not TELEGRAM_ENABLED:
        logger.warning("TELEGRAM_ENABLED no está habilitado. Saliendo.")
        return
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado. Saliendo.")
        return
    
    logger.info("=" * 60)
    logger.info("Iniciando Telegram Polling Worker...")
    logger.info(f"Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"Timeout de polling: {POLLING_TIMEOUT}s")
    logger.info(f"Retry delay: {POLLING_RETRY_DELAY}s")
    logger.info(f"DB_URL: {DB_URL[:50]}..." if len(DB_URL) > 50 else f"DB_URL: {DB_URL}")
    logger.info("=" * 60)
    
    # 0. Test de conexión con Telegram (verificar que el token es válido)
    logger.info("Verificando conexión con Telegram API...")
    try:
        test_url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/getMe"
        async with httpx.AsyncClient(timeout=10.0) as client:
            test_resp = await client.get(test_url)
            test_resp.raise_for_status()
            test_result = test_resp.json()
            if test_result.get("ok"):
                bot_info = test_result.get("result", {})
                bot_username = bot_info.get("username", "N/A")
                bot_id = bot_info.get("id", "N/A")
                logger.info(f"✓ Conexión exitosa con Telegram. Bot: @{bot_username} (ID: {bot_id})")
            else:
                logger.error(f"✗ Error verificando bot: {test_result.get('description', 'Unknown error')}")
                return
    except Exception as e:
        logger.error(f"✗ Error de conexión con Telegram API: {e}")
        logger.error("Verificar que TELEGRAM_BOT_TOKEN sea correcto y que haya conexión a internet")
        return
    
    # 1. Eliminar webhook (obligatorio antes de polling)
    logger.info("Eliminando webhook existente...")
    webhook_deleted = await delete_webhook(TELEGRAM_BOT_TOKEN)
    if webhook_deleted:
        # No duplicar el mensaje (ya se loguea en delete_webhook)
        pass
    else:
        logger.warning("⚠ No se pudo eliminar el webhook. Continuando de todas formas...")
    
    # 2. Inicializar offset
    last_update_id = 0
    logger.info(f"Offset inicial: {last_update_id}")
    
    # 3. Bucle principal
    logger.info("✓ Iniciando bucle de polling...")
    consecutive_errors = 0
    max_consecutive_errors = 5
    updates_processed = 0
    messages_processed = 0
    
    while True:
        try:
            # Obtener updates
            result = await get_updates(
                token=TELEGRAM_BOT_TOKEN,
                offset=last_update_id + 1 if last_update_id > 0 else None,
                timeout=POLLING_TIMEOUT,
            )
            
            if result is None:
                # Timeout normal o error de red, continuar
                consecutive_errors = 0
                logger.debug("Timeout en getUpdates (normal en long polling), continuando...")
                continue
            
            if not result.get("ok"):
                error_description = result.get("description", "Unknown error")
                logger.error(f"Error en getUpdates: {error_description}")
                consecutive_errors += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Demasiados errores consecutivos ({consecutive_errors}). Reintentando en {POLLING_RETRY_DELAY}s...")
                    await asyncio.sleep(POLLING_RETRY_DELAY)
                    consecutive_errors = 0
                continue
            
            # Procesar updates
            updates = result.get("result", [])
            if not updates:
                consecutive_errors = 0
                logger.debug("No hay updates nuevos, continuando polling...")
                continue  # No hay updates, continuar polling
            
            updates_processed += len(updates)
            
            logger.info(f"📥 Recibidos {len(updates)} updates de Telegram")
            
            for update in updates:
                update_id = update.get("update_id")
                if update_id:
                    last_update_id = max(last_update_id, update_id)
                
                # Extraer mensaje
                message = update.get("message") or update.get("edited_message")
                if not message:
                    logger.debug(f"Update {update_id} no contiene mensaje, saltando...")
                    continue
                
                chat = message.get("chat", {})
                chat_id = chat.get("id")
                text = message.get("text", "").strip()
                
                # Extraer file_id de foto (si existe)
                image_file_id = None
                photo = message.get("photo")
                if photo and isinstance(photo, list) and len(photo) > 0:
                    # Usar la foto más grande (última en la lista)
                    image_file_id = photo[-1].get("file_id")
                    logger.info(f"📷 Foto detectada en update {update_id}, file_id={image_file_id}")
                    # Si no hay texto pero hay foto, usar texto por defecto para diagnóstico
                    if not text:
                        text = "¿Qué le pasa a mi planta?"
                
                if not chat_id:
                    logger.warning(f"⚠ Update {update_id} no tiene chat_id, saltando...")
                    continue
                
                if not text and not image_file_id:
                    logger.debug(f"Update {update_id} no tiene texto ni imagen, saltando...")
                    continue  # Ignorar mensajes sin texto ni imagen
                
                logger.info(f"📨 Mensaje recibido de chat_id={chat_id}: {text[:50] if text else '(solo imagen)'}...")
                
                # Procesar mensaje de forma asíncrona (sin bloquear el loop)
                try:
                    asyncio.create_task(process_message(text, chat_id, image_file_id))
                    messages_processed += 1
                    logger.debug(f"✓ Tarea de procesamiento creada para chat_id={chat_id} (total procesados: {messages_processed})")
                except Exception as task_err:
                    logger.error(f"✗ Error creando tarea de procesamiento: {task_err}", exc_info=True)
            
            consecutive_errors = 0
            if updates_processed > 0 and updates_processed % 10 == 0:
                logger.info(f"📊 Estadísticas: {updates_processed} updates procesados, {messages_processed} mensajes procesados")
            
        except KeyboardInterrupt:
            logger.info("Interrupción recibida. Cerrando worker...")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error en bucle de polling: {e}", exc_info=True)
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Demasiados errores consecutivos ({consecutive_errors}). Esperando {POLLING_RETRY_DELAY}s antes de reintentar...")
                await asyncio.sleep(POLLING_RETRY_DELAY)
                consecutive_errors = 0
    
    logger.info("Worker de Telegram detenido.")


def main() -> None:
    """Función principal para ejecutar el worker."""
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        logger.info("Worker interrumpido por el usuario.")
    except Exception as e:
        logger.error(f"Error fatal en worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

