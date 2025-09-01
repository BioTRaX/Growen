# NG-HEADER: Nombre de archivo: ws.py
# NG-HEADER: Ubicación: services/routers/ws.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""WebSocket de chat que utiliza la IA de respaldo."""

from datetime import datetime
import asyncio
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import Session as DBSess
from db.session import SessionLocal
from starlette.websockets import WebSocketDisconnect, WebSocketState

from services.ai.provider import ai_reply

router = APIRouter()
logger = logging.getLogger(__name__)

# Intervalos en segundos para mantener la conexión
PING_INTERVAL = 30
READ_TIMEOUT = 60


async def _ping(socket: WebSocket) -> None:
    """Envía pings periódicos para sostener la conexión."""
    while True:
        await asyncio.sleep(PING_INTERVAL)
        if socket.client_state != WebSocketState.CONNECTED:
            break
        try:
            await socket.send_json({"role": "ping", "text": ""})
        except Exception as exc:  # pragma: no cover - logueo defensivo
            logger.debug("No se pudo enviar ping: %s", exc)
            break


@router.websocket("/ws")
async def ws_chat(socket: WebSocket) -> None:
    """Canal WebSocket principal."""

    # Buscar sesión para personalizar la conversación si el usuario está autenticado.
    sess = None
    sid = socket.cookies.get("growen_session")
    if sid:
        async with SessionLocal() as db:
            res = await db.execute(
                select(DBSess)
                .options(selectinload(DBSess.user))
                .where(DBSess.id == sid, DBSess.expires_at > datetime.utcnow())
            )
            sess = res.scalar_one_or_none()

    await socket.accept()
    ping_task = asyncio.create_task(_ping(socket))
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    socket.receive_text(), timeout=READ_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout de lectura en ws_chat")
                break

            # Personalizar el prompt con los datos del usuario/rol si hay sesión.
            prompt = data
            if sess:
                if sess.user:
                    nombre = sess.user.name or sess.user.identifier
                    prompt = f"{nombre} ({sess.role}) dice: {data}"
                else:
                    prompt = f"{sess.role} dice: {data}"

            reply = await ai_reply(prompt)
            await socket.send_json({"role": "assistant", "text": reply})
    except WebSocketDisconnect:
        # El cliente cerró la conexión; Starlette maneja el cierre y no
        # es necesario llamar a ``close`` manualmente.
        logger.warning("Cliente desconectado")
    except Exception as exc:
        logger.error("Error inesperado en ws_chat: %s", exc)
        if socket.client_state == WebSocketState.CONNECTED:
            try:
                await socket.send_json({"role": "system", "text": f"error: {exc}"})
            except Exception as send_exc:
                logger.error(
                    "No se pudo notificar al cliente del error: %s", send_exc
                )
    finally:
        ping_task.cancel()
        if socket.client_state == WebSocketState.CONNECTED:
            await socket.close()
