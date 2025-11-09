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
from typing import Optional

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
    extract_product_query,  # Solo parsing; lógica de resolución DEPRECATED
    resolve_price,
    serialize_result,
    render_product_response,
)
from services.chat.memory import (
    build_memory_key,
    clear_memory,
    ensure_memory,
    get_memory,
    mark_prompted,
    mark_resolved,
)
from services.chat.shared import (
    ALLOWED_PRODUCT_METRIC_ROLES,
    CLARIFY_CONFIRM_WORDS,
    clarify_prompt_text,
    memory_terms_text,
    normalize_followup_text,
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
    correlation_header = socket.headers.get("x-correlation-id") or socket.headers.get("x-request-id")
    base_correlation_id = correlation_header or f"ws-{uuid.uuid4().hex[:10]}"
    message_index = 0
    role = getattr(sess, "role", "anon") or "anon"
    host = getattr(socket.client, "host", None)
    user_agent = socket.headers.get("user-agent")
    memory_key = build_memory_key(session_id=sid, role=role, host=host, user_agent=user_agent)
    ping_task = asyncio.create_task(_ping(socket))
    try:
        while True:
            try:
                data = await asyncio.wait_for(socket.receive_text(), timeout=READ_TIMEOUT)
            except asyncio.TimeoutError:
                try:
                    logger.warning("Timeout de lectura en ws_chat", extra={"correlation_id": base_correlation_id})
                except Exception:
                    logger.warning("Timeout de lectura en ws_chat")
                break

            message_index += 1
            correlation_id = f"{base_correlation_id}:{message_index}"

            if not isinstance(data, str):
                await socket.send_json({"role": "system", "text": "Entrada invalida."})
                continue
            data = data.strip()
            if not data:
                await socket.send_json({"role": "system", "text": "Decime algo para responder."})
                continue
            if len(data) > 2000:
                await socket.send_json({"role": "system", "text": "Tu mensaje es muy largo. Por favor, resumilo (max. 2000 caracteres)."})
                continue

            memory_state = get_memory(memory_key)
            include_metrics = role in ALLOWED_PRODUCT_METRIC_ROLES

            product_query = extract_product_query(data)
            if product_query:
                # Nuevo flujo: delegar directamente a OpenAI tool-calling (MCP Products)
                ai_router = AIRouter(core_settings)
                provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
                chat_with_tools = getattr(provider, "chat_with_tools", None)
                if callable(chat_with_tools):
                    try:
                        answer = await chat_with_tools(prompt=data, user_role=role)
                        # Para mantener compatibilidad de clientes, emitimos type=product_answer simplificado
                        await socket.send_json({
                            "role": "assistant",
                            "text": answer,
                            "type": "product_answer",
                            "intent": "product_tool",
                        })
                        # No utilizamos memoria de ambigüedad en el nuevo flujo (MVP)
                        clear_memory(memory_key)
                        continue
                    except Exception:
                        logger.exception("ws.tool_call_error")
                        await socket.send_json({
                            "role": "assistant",
                            "text": "Error consultando información de producto.",
                            "type": "error",
                        })
                        continue
                # Fallback local sin tools: usar resolver interno (compat WS/tests)
                try:
                    async with SessionLocal() as db:
                        result = await resolve_price(data, db, limit=5)
                    payload = serialize_result(result, include_metrics=include_metrics)
                    text = render_product_response(result)
                    await socket.send_json({
                        "role": "assistant",
                        "text": text,
                        "type": "product_answer",
                        "intent": result.intent,
                        "data": payload,
                    })
                    clear_memory(memory_key)
                except Exception:
                    logger.exception("ws.local_price_fallback_error")
                    await socket.send_json({
                        "role": "assistant",
                        "text": "Error resolviendo información de producto.",
                        "type": "error",
                    })
                continue

            if memory_state and memory_state.pending_clarification:
                normalized = normalize_followup_text(data)
                if not normalized:
                    mark_prompted(memory_key)
                    terms = memory_terms_text(memory_state.query)
                    try:
                        logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id, "terms": terms})
                    except Exception:
                        pass
                    await socket.send_json({
                        "role": "assistant",
                        "type": "clarify_prompt",
                        "intent": "clarify",
                        "text": clarify_prompt_text(terms),
                    })
                    continue
                if normalized in CLARIFY_CONFIRM_WORDS:
                    # Nuevo flujo: pedimos al usuario reformular con SKU exacto en lugar de relanzar ranking local
                    await socket.send_json({
                        "role": "assistant",
                        "text": "Por favor pedime nuevamente el producto indicando el SKU exacto para darte precio y stock actualizado.",
                        "type": "clarify_ack",
                        "intent": "clarify",
                    })
                    clear_memory(memory_key)
                    continue
                tokens = normalized.split()
                if len(tokens) <= 3 and not memory_state.prompted:
                    mark_prompted(memory_key)
                    terms = memory_terms_text(memory_state.query)
                    try:
                        logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id, "terms": terms})
                    except Exception:
                        pass
                    await socket.send_json({
                        "role": "assistant",
                        "type": "clarify_prompt",
                        "intent": "clarify",
                        "text": clarify_prompt_text(terms),
                    })
                    continue

            if memory_state and not memory_state.pending_clarification:
                clear_memory(memory_key)

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
                    extra={"correlation_id": correlation_id},
                )
                acc = []
                try:
                    for chunk in router_ai.run_stream(Task.SHORT_ANSWER.value, prompt):
                        if not acc and (chunk.startswith("openai:") or chunk.startswith("ollama:")):
                            _, _, chunk = chunk.partition(":")
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
                                extra={"correlation_id": correlation_id},
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
                        extra={"correlation_id": correlation_id},
                    )
                    logger.info(
                        "ws_chat message",
                        extra={
                            "prompt_chars": len(prompt),
                            "reply_chars": len(full),
                            "duration_ms": int((time.perf_counter() - t0) * 1000),
                            "auth": bool(sess),
                            "stream": True,
                            "correlation_id": correlation_id,
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
                        "[ai:request] task=%s auth=%s prompt_chars=%s",
                        Task.SHORT_ANSWER.value,
                        bool(sess),
                        len(prompt),
                        extra={"correlation_id": correlation_id},
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
                        "correlation_id": correlation_id,
                    },
                )
    except WebSocketDisconnect:
        logger.warning("Cliente desconectado")
    except Exception as exc:
        logger.error("Error inesperado en ws_chat: %s", exc)
        if socket.client_state == WebSocketState.CONNECTED:
            try:
                await socket.send_json({"role": "system", "text": f"error: {exc}"})
            except Exception as send_exc:
                logger.error("No se pudo notificar al cliente del error: %s", send_exc)
    finally:
        ping_task.cancel()
        if socket.client_state == WebSocketState.CONNECTED:
            await socket.close()

