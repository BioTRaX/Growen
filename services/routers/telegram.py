#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: telegram.py
# NG-HEADER: Ubicación: services/routers/telegram.py
# NG-HEADER: Descripción: Webhook de Telegram que redirige mensajes al pipeline de chat actual
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from services.notifications.telegram import send_message as tg_send
from services.chat.price_lookup import (
    extract_product_query,
    log_product_lookup,
    render_product_response,
    resolve_product_info,
)
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

    # Extraer chat_id y texto
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = (message.get("chat") or {})
    chat_id = chat.get("id")
    text = message.get("text") or ""
    if not chat_id or not text:
        return {"ok": True}  # silencioso para otras actualizaciones

    # 1) Intento controlado: consulta de precio
    product_query = extract_product_query(text)
    if product_query:
        result = await resolve_product_info(product_query, db)
        reply = render_product_response(result)
        await tg_send(reply, chat_id=str(chat_id))
        try:
            await log_product_lookup(
                db,
                user_id=None,
                ip=None,
                original_text=text,
                product_query=product_query,
                result=result,
            )
        except Exception:
            pass
        return {"ok": True}

    # 2) Fallback al router de IA con el mismo prompt/persona del chat HTTP
    ai_router = AIRouter(core_settings)
    raw = ai_router.run(Task.SHORT_ANSWER.value, text)
    if "\n\n" in raw:
        reply = raw.split("\n\n")[-1].strip()
    else:
        reply = raw.strip()
    await tg_send(reply, chat_id=str(chat_id))
    return {"ok": True}
