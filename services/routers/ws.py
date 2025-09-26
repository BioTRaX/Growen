# NG-HEADER: Nombre de archivo: ws.py
# NG-HEADER: Ubicación: services/routers/ws.py
# NG-HEADER: Descripción: WebSocket de chat que canaliza prompts al AIRouter (OpenAI/Ollama) y emite respuestas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""WebSocket de chat que utiliza la IA de respaldo.

Flujo:
- El cliente envía texto plain.
- Se contextualiza con la sesión (si existe) para añadir nombre y rol.
- Se invoca `AIRouter.run` con la tarea `short_answer` (ahora soportada por OpenAI).
- Se normaliza y se retorna como `{role: "assistant", text: ...}`.

Logs añadidos:
- `[ai:request]` DEBUG: caracteres del prompt y si hay auth.
- `[ai:response]` DEBUG: proveedor detectado, duración y tamaño respuesta.
- INFO final por mensaje: `ws_chat message` con métricas agregadas.
"""

from datetime import datetime
import time
import asyncio
import os
import uuid
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import Session as DBSess
from db.session import SessionLocal
from starlette.websockets import WebSocketDisconnect, WebSocketState

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from services.chat.price_lookup import (
    extract_product_query,
    log_product_lookup,
    render_product_response,
    resolve_product_info,
    serialize_result,
)

router = APIRouter()
logger = logging.getLogger(__name__)
try:  # inicializa logger AI separado si corresponde
    from ai.logging_setup import setup_ai_logger
    setup_ai_logger()
except Exception:  # pragma: no cover
    pass

# Intervalos en segundos para mantener la conexión
PING_INTERVAL = 30
READ_TIMEOUT = 60
async def ai_reply(prompt: str) -> str:
    """Genera una respuesta breve usando AIRouter.

    Expuesta como función aparte para permitir monkeypatch en tests.
    Añadimos logging granular de latencia y proveedor efectivo.
    """
    router = AIRouter(core_settings)
    t0 = time.perf_counter()
    raw_reply = router.run(Task.SHORT_ANSWER.value, prompt)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    provider = None
    try:
        # Heurística de provider desde prefijo (openai:/ollama:). Si no, unknown.
        if raw_reply.startswith("openai:"):
            provider = "openai"
        elif raw_reply.startswith("ollama:"):
            provider = "ollama"
        logger.debug(
            "[ai:response] provider=%s ms=%s chars=%s", provider, duration_ms, len(raw_reply)
        )
    except Exception:  # pragma: no cover - logging defensivo
        pass
    if "\n\n" in raw_reply:
        return raw_reply.split("\n\n")[-1].strip()
    return raw_reply.strip()



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

            # Saneamiento básico y límites para evitar abuso del canal
            if not isinstance(data, str):
                await socket.send_json({"role": "system", "text": "Entrada inválida."})
                continue
            data = data.strip()
            if not data:
                await socket.send_json({"role": "system", "text": "Decime algo para responder."})
                continue
            if len(data) > 2000:
                await socket.send_json({
                    "role": "system",
                    "text": "Tu mensaje es muy largo. Por favor, resumilo (máx. 2000 caracteres).",
                })
                continue

            product_query = extract_product_query(data)
            if product_query:
                # Resolver consultas de producto de forma determinista evitando delegar al streaming.
                async with SessionLocal() as db:
                    result = await resolve_product_info(product_query, db)
                    await log_product_lookup(
                        db,
                        user_id=(sess.user.id if getattr(sess, "user", None) else None),
                        ip=getattr(socket.client, "host", None),
                        original_text=data,
                        product_query=product_query,
                        result=result,
                    )
                payload = serialize_result(result)
                await socket.send_json({
                    "role": "assistant",
                    "text": render_product_response(result),
                    "type": "product_answer",
                    "data": payload,
                    "intent": result.intent,
                    "took_ms": result.took_ms,
                })
                continue

            # Personalizar el prompt con los datos del usuario/rol si hay sesión.
            t0 = time.perf_counter()
            prompt = data
            if sess:
                if sess.user:
                    nombre = sess.user.name or sess.user.identifier
                    prompt = f"{nombre} ({sess.role}) dice: {data}"
                else:
                    prompt = f"{sess.role} dice: {data}"
            streaming_enabled = os.getenv("AI_STREAM_WS", "false").lower() in {"1", "true", "yes"}
            if streaming_enabled:
                router_ai = AIRouter(core_settings)
                msg_id = uuid.uuid4().hex
                await socket.send_json({"role": "assistant", "stream": "start", "id": msg_id})
                logger.debug(
                    "[ai:stream:start] id=%s task=%s auth=%s prompt_chars=%s",
                    msg_id,
                    Task.SHORT_ANSWER.value,
                    bool(sess),
                    len(prompt),
                )
                acc = []
                try:
                    for chunk in router_ai.run_stream(Task.SHORT_ANSWER.value, prompt):
                        # chunk incluye prefijo openai:/ollama: en el primer fragmento; eliminamos al vuelo
                        if not acc and (chunk.startswith("openai:") or chunk.startswith("ollama:")):
                            # quitar prefijo sólo primera vez
                            _, _, chunk = chunk.partition(":")
                        # Delta puro
                        if chunk:
                            acc.append(chunk)
                            await socket.send_json({
                                "role": "assistant",
                                "stream": "chunk",
                                "id": msg_id,
                                "text": chunk,
                            })
                            logger.debug(
                                "[ai:stream:chunk] id=%s delta_chars=%s total_chars=%s",
                                msg_id,
                                len(chunk),
                                sum(len(c) for c in acc),
                            )
                    full = "".join(acc).strip()
                    await socket.send_json({
                        "role": "assistant",
                        "stream": "end",
                        "id": msg_id,
                        "text": full,
                        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                    })
                    logger.debug(
                        "[ai:stream:end] id=%s total_chars=%s ms=%s",
                        msg_id,
                        len(full),
                        int((time.perf_counter() - t0) * 1000),
                    )
                    logger.info(
                        "ws_chat message",
                        extra={
                            "prompt_chars": len(prompt),
                            "reply_chars": len(full),
                            "duration_ms": int((time.perf_counter() - t0) * 1000),
                            "auth": bool(sess),
                            "stream": True,
                        },
                    )
                except Exception as exc:  # pragma: no cover
                    logger.error("Error streaming ws_chat: %s", exc)
                    await socket.send_json({
                        "role": "system",
                        "stream": "error",
                        "id": msg_id,
                        "error": str(exc),
                    })
            else:
                try:
                    logger.debug(
                        "[ai:request] task=%s auth=%s prompt_chars=%s", Task.SHORT_ANSWER.value, bool(sess), len(prompt)
                    )
                    raw_reply = await ai_reply(prompt)
                except Exception as exc:  # pragma: no cover
                    logger.error("Error inesperado en ws_chat: %s", exc)
                    await socket.send_json({"role": "system", "text": f"error: {exc}"})
                    continue
                reply = raw_reply.strip()
                await socket.send_json({"role": "assistant", "text": reply})
                logger.info(
                    "ws_chat message",
                    extra={
                        "prompt_chars": len(prompt),
                        "reply_chars": len(reply),
                        "duration_ms": int((time.perf_counter() - t0) * 1000),
                        "auth": bool(sess),
                        "stream": False,
                    },
                )
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
