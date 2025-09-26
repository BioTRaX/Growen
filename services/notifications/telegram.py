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
    try:
        enabled = os.getenv("TELEGRAM_ENABLED", "0").lower() in ("1", "true", "yes")
    except Exception:
        enabled = False
    if not enabled:
        return False

    tok = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_DEFAULT_CHAT_ID")
    if not tok or not chat or httpx is None:
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
            return resp.status_code == 200
    except Exception:
        return False

