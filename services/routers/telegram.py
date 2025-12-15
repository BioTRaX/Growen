#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: telegram.py
# NG-HEADER: Ubicación: services/routers/telegram.py
# NG-HEADER: Descripción: Webhook de Telegram que redirige mensajes al pipeline de chat actual
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException

from services.notifications.telegram import send_message as tg_send
from services.chat.telegram_handler import handle_telegram_message
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session
from fastapi import Depends

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    """Webhook compatible con Telegram.

    - Protegido por path token (TELEGRAM_WEBHOOK_TOKEN) y header opcional X-Telegram-Bot-Api-Secret-Token.
    - Procesa mensajes de texto -> ejecuta el pipeline de chat actual.
    - Responde al mismo chat vía sendMessage.
    """
    expected_token = os.getenv("TELEGRAM_WEBHOOK_TOKEN")
    if not expected_token or token != expected_token:
        raise HTTPException(status_code=404, detail="Not found")

    # Validación opcional de secret header
    secret_expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_expected and (secret_header or "") != secret_expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Extraer chat_id, texto e imagen
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = (message.get("chat") or {})
    chat_id = chat.get("id")
    text = message.get("text") or ""
    
    # Extraer file_id de foto (si existe)
    image_file_id = None
    photo = message.get("photo")
    if photo and isinstance(photo, list) and len(photo) > 0:
        # Usar la foto más grande (última en la lista)
        image_file_id = photo[-1].get("file_id")
        # Si no hay texto pero hay foto, usar texto por defecto para diagnóstico
        if not text:
            text = "¿Qué le pasa a mi planta?"
    
    if not chat_id or (not text and not image_file_id):
        return {"ok": True}  # silencioso para otras actualizaciones

    # Procesar mensaje usando el handler compartido
    logger = logging.getLogger(__name__)
    try:
        answer = await handle_telegram_message(
            text=text, 
            chat_id=str(chat_id), 
            db=db,
            image_file_id=image_file_id,  # Pasar file_id si existe
        )
        await tg_send(answer, chat_id=str(chat_id))
    except Exception as e:
        # Log del error pero no exponer detalles al usuario
        logger.error(f"Error procesando mensaje de Telegram: {e}", exc_info=True)
        await tg_send("Disculpá, hubo un error procesando tu mensaje. Probá más tarde.", chat_id=str(chat_id))
    
    return {"ok": True}
