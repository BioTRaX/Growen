#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: telegram.py
# NG-HEADER: Ubicación: services/notifications/telegram.py
# NG-HEADER: Descripción: Envío de mensajes a Telegram con feature flag y overrides
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
from typing import Optional

try:  # httpx opcional; si no está, el envío se omite silenciosamente
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


async def send_message(
    text: str,
    *,
    chat_id: Optional[str | int] = None,
    token: Optional[str] = None,
    timeout: float = 6.0,
    parse_mode: Optional[str] = None,
) -> bool:
    """Envía un mensaje de texto a Telegram si la integración está habilitada.

    - Respeta flag TELEGRAM_ENABLED (1/true) para habilitar/omitir.
    - Usa token/chat_id provistos, o defaults de entorno:
      TELEGRAM_BOT_TOKEN / TELEGRAM_DEFAULT_CHAT_ID.
    - No levanta excepciones: devuelve True si intentó y fue 200 OK, False si omitió o falló.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        enabled = os.getenv("TELEGRAM_ENABLED", "0").lower() in ("1", "true", "yes")
    except Exception:
        enabled = False
    if not enabled:
        logger.debug("TELEGRAM_ENABLED no está habilitado, omitiendo envío")
        return False

    tok = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_DEFAULT_CHAT_ID")
    if not tok:
        logger.warning("TELEGRAM_BOT_TOKEN no está configurado, no se puede enviar mensaje")
        return False
    if not chat:
        logger.warning(f"chat_id no proporcionado y TELEGRAM_DEFAULT_CHAT_ID no configurado, no se puede enviar mensaje")
        return False
    if httpx is None:
        logger.warning("httpx no está disponible, no se puede enviar mensaje")
        return False
    
    try:
        payload = {"chat_id": chat, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        async with httpx.AsyncClient(timeout=timeout) as client:  # type: ignore
            resp = await client.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                json=payload,
            )
            if resp.status_code == 200:
                logger.debug(f"✓ Mensaje enviado exitosamente a chat_id={chat}")
                return True
            else:
                # Log del error de Telegram API
                try:
                    error_data = resp.json()
                    error_code = error_data.get("error_code")
                    description = error_data.get("description", "Unknown error")
                    logger.error(f"✗ Error enviando mensaje a chat_id={chat}: code={error_code}, description={description}")
                except Exception:
                    logger.error(f"✗ Error enviando mensaje a chat_id={chat}: HTTP {resp.status_code} - {resp.text[:200]}")
                return False
    except httpx.TimeoutException:
        logger.error(f"✗ Timeout enviando mensaje a chat_id={chat}")
        return False
    except Exception as e:
        logger.error(f"✗ Excepción enviando mensaje a chat_id={chat}: {type(e).__name__}: {e}", exc_info=True)
        return False


async def download_telegram_file(
    file_id: str,
    token: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[bytes]:
    """
    Descarga un archivo desde Telegram usando su File ID.
    
    Args:
        file_id: File ID del archivo en Telegram
        token: Token del bot (opcional, usa TELEGRAM_BOT_TOKEN por defecto)
        timeout: Timeout en segundos
        
    Returns:
        Contenido del archivo como bytes, o None si falla
        
    Notas:
        - File IDs de Telegram son temporales (válidos ~24 horas para fotos)
        - Límite de tamaño: 20MB (límite de OpenAI Vision)
        - Formatos soportados: JPEG, PNG, WebP
    """
    if not file_id or httpx is None:
        return None
    
    tok = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not tok:
        return None
    
    try:
        # Paso 1: Obtener file_path usando getFile
        async with httpx.AsyncClient(timeout=timeout) as client:  # type: ignore
            get_file_url = f"https://api.telegram.org/bot{tok}/getFile"
            get_file_resp = await client.get(get_file_url, params={"file_id": file_id})
            get_file_resp.raise_for_status()
            file_info = get_file_resp.json()
            
            if not file_info.get("ok"):
                return None
            
            file_path = file_info.get("result", {}).get("file_path")
            if not file_path:
                return None
            
            # Validar tamaño (límite 20MB para OpenAI)
            file_size = file_info.get("result", {}).get("file_size", 0)
            if file_size > 20 * 1024 * 1024:  # 20MB
                return None
            
            # Paso 2: Descargar el archivo usando file_path
            download_url = f"https://api.telegram.org/file/bot{tok}/{file_path}"
            download_resp = await client.get(download_url, timeout=timeout)
            download_resp.raise_for_status()
            
            return download_resp.content
            
    except Exception:
        return None
