# NG-HEADER: Nombre de archivo: ws.py
# NG-HEADER: Ubicación: services/routers/ws.py
# NG-HEADER: Descripción: Adaptador WebSocket del pipeline multicanal observable de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""WebSocket de chat integrado con identidad, historial y observabilidad.

Flujo:
- El cliente envía texto plain.
- Se recarga la sesión y el rol efectivo en cada mensaje.
- Las rutas principales se ejecutan mediante `ChatOrchestrator`.
- Se normaliza y se retorna como `{role: "assistant", text: ...}`.

Logs añadidos:
- `[ai:request]` DEBUG: caracteres del prompt y si hay auth.
- `[ai:response]` DEBUG: proveedor detectado, duración y tamaño respuesta.
- INFO final por mensaje: `ws_chat message` con métricas agregadas.
"""

from datetime import datetime
from dataclasses import dataclass, field
import time
import asyncio
import os
import uuid
import logging
import hashlib
from typing import Any, Optional

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import Session as DBSess
from db.session import SessionLocal
from services.auth import hash_session_id
from services.chat.history import save_message, get_recent_history
from services.chat.orchestrator import ChatRequestContext, chat_orchestrator
from starlette.websockets import WebSocketDisconnect, WebSocketState

from agent_core.config import settings as core_settings
from agent_core.chat_policy import public_product_result
from ai.router import AIRouter
from ai.types import Task
from services.chat.price_lookup import (
    extract_product_query,  # Solo parsing; lógica de resolución DEPRECATED
    resolve_price,
    serialize_result,
    render_product_response_for_role,
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


@dataclass
class WebSocketReply:
    """Respuesta mutable para que el orquestador adjunte citas RAG."""

    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)


async def _load_active_session(db, raw_sid: str | None) -> DBSess | None:
    """Resuelve sesión y usuario actuales; debe invocarse para cada mensaje."""

    if not raw_sid:
        return None
    return await db.scalar(
        select(DBSess)
        .options(selectinload(DBSess.user))
        .where(DBSess.id == hash_session_id(raw_sid), DBSess.expires_at > datetime.utcnow())
        .execution_options(populate_existing=True)
    )


def _build_prompt_with_history(history: str, user_text: str) -> str:
    """Concatena historial formateado con el mensaje actual."""
    if history:
        return f"{history}\n\nUsuario: {user_text}"
    return user_text


async def _add_rag_context(
    prompt: str,
    query: str,
    db_session,
    *,
    role: str,
) -> str:
    """Añade únicamente conocimiento autorizado para el canal WebSocket."""

    from services.rag.search import get_rag_search_service

    context = await get_rag_search_service().search_and_format_context(
        query=query,
        session=db_session,
        top_k=3,
        min_similarity=0.5,
        role=role,
        channel="websocket",
    )
    if not context:
        return prompt
    return (
        f"{prompt}\n\nContexto autorizado de Growen:\n{context}\n"
        "Usá el contexto sólo cuando sea pertinente y no inventes datos ausentes."
    )


def _strip_provider_prefix(text: str) -> str:
    """Quita prefijos técnicos (openai:/ollama:) antes de guardar o responder."""
    if ":" in text:
        prefix = text.split(":", 1)[0]
        if prefix in {"openai", "ollama"}:
            return text.split(":", 1)[1].strip()
    return text.strip()


async def _persist_chat_history(
    db_session,
    session_id: str,
    user_text: str,
    assistant_text: str,
    intent: str,
    response_type: str,
    user_identifier: Optional[str] = None,
) -> None:
    """Guarda el intercambio en la tabla chat_messages."""
    try:
        # Extraer user_identifier del session_id si no se proporciona
        if not user_identifier:
            if session_id.startswith("web:"):
                user_identifier = session_id[4:]
            elif session_id.startswith("telegram:"):
                user_identifier = session_id[9:]
            else:
                user_identifier = session_id
        
        await save_message(db_session, session_id, "user", user_text, metadata={"intent": intent}, user_identifier=user_identifier)
        await save_message(db_session, session_id, "assistant", assistant_text, metadata={"type": response_type}, user_identifier=user_identifier)
        await db_session.commit()
    except Exception:
        logger.exception("ws.chat_history_save_error")


async def _emit_orchestrated_response(
    socket: WebSocket,
    db_session,
    context: ChatRequestContext,
    *,
    session_id: str,
    user_text: str,
    assistant_text: str,
    response_type: str,
    intent: str,
    user_identifier: str,
    extra: dict | None = None,
) -> None:
    """Emite y persiste respuestas deterministas dentro del pipeline común."""

    async def operation() -> dict:
        return {"text": assistant_text, "type": response_type, "intent": intent}

    result = await chat_orchestrator.execute(db_session, context, operation, input_text=user_text)
    payload = {"role": "assistant", **result, "correlation_id": context.correlation_id}
    if extra:
        payload.update(extra)
    await socket.send_json(payload)
    await _persist_chat_history(
        db_session,
        session_id,
        user_text,
        assistant_text,
        intent=intent,
        response_type=response_type,
        user_identifier=user_identifier,
    )

async def ai_reply(prompt: str) -> str:
    """Genera una respuesta breve usando AIRouter.

    Expuesta como función aparte para permitir monkeypatch en tests.
    Añadimos logging granular de latencia y proveedor efectivo.
    """
    router = AIRouter(core_settings)
    t0 = time.perf_counter()
    raw_reply = await router.run_async(Task.SHORT_ANSWER.value, prompt)
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
            logger.debug("No se pudo enviar ping error=%s", type(exc).__name__)
            break


@router.websocket("/ws")
async def ws_chat(socket: WebSocket) -> None:
    """Canal WebSocket principal."""

    sess = None
    sid = socket.cookies.get("growen_session")
    if sid:
        async with SessionLocal() as db:
            sess = await _load_active_session(db, sid)

    host = getattr(socket.client, "host", "unknown")
    user_agent = socket.headers.get("user-agent", "unknown")
    if sid:
        # Agregar prefijo "web:" para identificar sesiones web
        chat_session_id = f"web:{hash_session_id(sid)}"
    else:
        # Fallback: generar ID basado en IP + user agent
        raw = f"{host}_{user_agent}"
        hash_id = hashlib.md5(raw.encode()).hexdigest()[:16]
        chat_session_id = f"web:{hash_id}"
    
    # Extraer user_identifier para guardar en sesión
    user_identifier = f"web:{chat_session_id.split(':', 1)[-1][:24]}"
    if not user_identifier:
        # Fallback: extraer del session_id (después del prefijo "web:")
        user_identifier = chat_session_id[4:] if chat_session_id.startswith("web:") else chat_session_id

    await socket.accept()
    correlation_header = socket.headers.get("x-correlation-id") or socket.headers.get("x-request-id")
    base_correlation_id = correlation_header or f"ws-{uuid.uuid4().hex[:10]}"
    message_index = 0
    role = getattr(getattr(sess, "user", None), "role", None) or getattr(sess, "role", "guest") or "guest"
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
                await socket.send_json({"role": "system", "text": "Entrada invalida.", "correlation_id": correlation_id})
                continue
            data = data.strip()
            if not data:
                await socket.send_json({"role": "system", "text": "Decime algo para responder.", "correlation_id": correlation_id})
                continue
            if len(data) > 2000:
                await socket.send_json({"role": "system", "text": "Tu mensaje es muy largo. Por favor, resumilo (max. 2000 caracteres).", "correlation_id": correlation_id})
                continue

            async with SessionLocal() as chat_db:
                if sid:
                    sess = await _load_active_session(chat_db, sid)
                role = getattr(getattr(sess, "user", None), "role", None) or getattr(sess, "role", "guest") or "guest"
                context = ChatRequestContext.build(
                    channel="websocket",
                    conversation_id=chat_session_id,
                    account_role=role,
                    user_id=getattr(getattr(sess, "user", None), "id", None),
                    correlation_id=correlation_id,
                )
                history_context = await get_recent_history(chat_db, chat_session_id, max_tokens=core_settings.chat_history_max_tokens)

                memory_state = get_memory(memory_key)
                include_metrics = role in ALLOWED_PRODUCT_METRIC_ROLES

                product_query = extract_product_query(data)
                if product_query:
                    # Flujo principal: usar run_async con tools_schema (OpenAI + MCP Products)
                    ai_router = AIRouter(core_settings)
                    provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
                    
                    # Obtener el schema de herramientas para consulta de productos
                    tools_schema = None
                    if hasattr(provider, 'build_tools_schema'):
                        tools_schema = await provider.build_tools_schema(role, "websocket")
                    
                    if tools_schema:
                        try:
                            prompt_with_history = _build_prompt_with_history(history_context, data)
                            answer_raw = await chat_orchestrator.execute(
                                chat_db,
                                context,
                                lambda: ai_router.run_async(
                                    task=Task.SHORT_ANSWER.value,
                                    prompt=prompt_with_history,
                                    user_context={"role": role, "channel": "websocket", "intent": "product_lookup"},
                                    tools_schema=tools_schema,
                                ),
                                input_text=prompt_with_history,
                            )
                            answer = _strip_provider_prefix(answer_raw)
                            await socket.send_json({
                                "role": "assistant",
                                "text": answer,
                                "type": "product_answer",
                                "intent": "product_tool",
                                "correlation_id": correlation_id,
                            })
                            await _persist_chat_history(
                                chat_db,
                                chat_session_id,
                                data,
                                answer,
                                intent="product_tool",
                                response_type="product_answer",
                                user_identifier=user_identifier,
                            )
                            clear_memory(memory_key)
                            continue
                        except Exception:
                            logger.exception("ws.tool_call_error")
                            await socket.send_json({
                                "role": "assistant",
                                "text": "Error consultando información de producto.",
                                "type": "error",
                                "correlation_id": correlation_id,
                            })
                            await _persist_chat_history(
                                chat_db,
                                chat_session_id,
                                data,
                                "Error consultando información de producto.",
                                intent="product_tool_error",
                                response_type="error",
                                user_identifier=user_identifier,
                            )
                            continue
                    # Fallback local sin tools: usar resolver interno (compat WS/tests)
                    try:
                        result = await chat_orchestrator.execute(
                            chat_db,
                            context,
                            lambda: resolve_price(data, chat_db, limit=5),
                            input_text=data,
                        )
                        payload = public_product_result(
                            serialize_result(result, include_metrics=include_metrics),
                            context.effective_role,
                        )
                        text = render_product_response_for_role(result, context.effective_role)
                        await socket.send_json({
                            "role": "assistant",
                            "text": text,
                            "type": "product_answer",
                            "intent": result.intent,
                            "data": payload,
                            "correlation_id": correlation_id,
                        })
                        await _persist_chat_history(
                            chat_db,
                            chat_session_id,
                            data,
                            text,
                            intent=result.intent or "product_fallback",
                            response_type="product_answer",
                            user_identifier=user_identifier,
                        )
                        clear_memory(memory_key)
                    except Exception:
                        logger.exception("ws.local_price_fallback_error")
                        error_text = "Error resolviendo información de producto."
                        await socket.send_json({
                            "role": "assistant",
                            "text": error_text,
                            "type": "error",
                            "correlation_id": correlation_id,
                        })
                        await _persist_chat_history(
                            chat_db,
                            chat_session_id,
                            data,
                            error_text,
                            intent="product_fallback_error",
                            response_type="error",
                            user_identifier=user_identifier,
                        )
                    continue

                if memory_state and memory_state.pending_clarification:
                    normalized = normalize_followup_text(data)
                    if not normalized:
                        mark_prompted(memory_key)
                        terms = memory_terms_text(memory_state.query)
                        try:
                            logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id})
                        except Exception:
                            pass
                        await _emit_orchestrated_response(
                            socket, chat_db, context,
                            session_id=chat_session_id,
                            user_text=data,
                            assistant_text=clarify_prompt_text(terms),
                            response_type="clarify_prompt",
                            intent="clarify",
                            user_identifier=user_identifier,
                        )
                        continue
                    if normalized in CLARIFY_CONFIRM_WORDS:
                        # Nuevo flujo: pedimos al usuario reformular con SKU exacto en lugar de relanzar ranking local
                        await _emit_orchestrated_response(
                            socket, chat_db, context,
                            session_id=chat_session_id,
                            user_text=data,
                            assistant_text="Por favor pedime nuevamente el producto indicando el SKU exacto para darte precio y stock actualizado.",
                            response_type="clarify_ack",
                            intent="clarify",
                            user_identifier=user_identifier,
                        )
                        clear_memory(memory_key)
                        continue
                    tokens = normalized.split()
                    if len(tokens) <= 3 and not memory_state.prompted:
                        mark_prompted(memory_key)
                        terms = memory_terms_text(memory_state.query)
                        try:
                            logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id})
                        except Exception:
                            pass
                        await _emit_orchestrated_response(
                            socket, chat_db, context,
                            session_id=chat_session_id,
                            user_text=data,
                            assistant_text=clarify_prompt_text(terms),
                            response_type="clarify_prompt",
                            intent="clarify",
                            user_identifier=user_identifier,
                        )
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
                prompt_with_history = _build_prompt_with_history(history_context, prompt)

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
                        len(prompt_with_history),
                        extra={"correlation_id": correlation_id},
                    )
                    try:
                        async def stream_operation() -> WebSocketReply:
                            enriched_prompt = await _add_rag_context(
                                prompt_with_history,
                                data,
                                chat_db,
                                role=context.effective_role,
                            )
                            chunks: list[str] = []
                            for chunk in router_ai.run_stream(Task.SHORT_ANSWER.value, enriched_prompt):
                                if not chunks and (chunk.startswith("openai:") or chunk.startswith("ollama:")):
                                    _, _, chunk = chunk.partition(":")
                                if chunk:
                                    chunks.append(chunk)
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
                                        sum(len(item) for item in chunks),
                                        extra={"correlation_id": correlation_id},
                                    )
                            return WebSocketReply(text="".join(chunks).strip())

                        full = await chat_orchestrator.execute(
                            chat_db,
                            context,
                            stream_operation,
                            input_text=prompt_with_history,
                        )
                        await socket.send_json({
                            "role": "assistant",
                            "stream": "end",
                            "id": msg_id,
                            "text": full.text,
                            "citations": full.citations,
                            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                            "correlation_id": correlation_id,
                        })
                        logger.debug(
                            "[ai:stream:end] id=%s total_chars=%s ms=%s",
                            msg_id,
                            len(full.text),
                            int((time.perf_counter() - t0) * 1000),
                            extra={"correlation_id": correlation_id},
                        )
                        logger.info(
                            "ws_chat message",
                            extra={
                                "prompt_chars": len(prompt_with_history),
                                "reply_chars": len(full.text),
                                "duration_ms": int((time.perf_counter() - t0) * 1000),
                                "auth": bool(sess),
                                "stream": True,
                                "correlation_id": correlation_id,
                            },
                        )
                        await _persist_chat_history(
                            chat_db,
                            chat_session_id,
                            data,
                            full.text,
                            intent="general",
                            response_type="assistant_stream",
                            user_identifier=user_identifier,
                        )
                    except Exception as exc:  # pragma: no cover
                        logger.error("Error streaming ws_chat: %s", type(exc).__name__)
                        await socket.send_json({
                            "role": "system",
                            "stream": "error",
                            "id": msg_id,
                            "error": "stream_failed",
                            "correlation_id": correlation_id,
                        })
                else:
                    try:
                        logger.debug(
                            "[ai:request] task=%s auth=%s prompt_chars=%s",
                            Task.SHORT_ANSWER.value,
                            bool(sess),
                            len(prompt_with_history),
                            extra={"correlation_id": correlation_id},
                        )
                        async def reply_operation() -> WebSocketReply:
                            enriched_prompt = await _add_rag_context(
                                prompt_with_history,
                                data,
                                chat_db,
                                role=context.effective_role,
                            )
                            return WebSocketReply(text=await ai_reply(enriched_prompt))

                        raw_reply = await chat_orchestrator.execute(
                            chat_db, context, reply_operation, input_text=prompt_with_history
                        )
                    except Exception as exc:  # pragma: no cover
                        logger.error("Error inesperado en ws_chat: %s", type(exc).__name__)
                        await socket.send_json({"role": "system", "text": "No pude procesar el mensaje.", "correlation_id": correlation_id})
                        continue
                    reply = _strip_provider_prefix(raw_reply.text.strip())
                    await socket.send_json({"role": "assistant", "text": reply, "citations": raw_reply.citations, "correlation_id": correlation_id})
                    logger.info(
                        "ws_chat message",
                        extra={
                            "prompt_chars": len(prompt_with_history),
                            "reply_chars": len(reply),
                            "duration_ms": int((time.perf_counter() - t0) * 1000),
                            "auth": bool(sess),
                            "stream": False,
                            "correlation_id": correlation_id,
                        },
                    )
                    await _persist_chat_history(
                        chat_db,
                        chat_session_id,
                        data,
                        reply,
                        intent="general",
                        response_type="assistant_message",
                    )
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as exc:
        logger.error("Error inesperado en ws_chat: %s", type(exc).__name__)
        if socket.client_state == WebSocketState.CONNECTED:
            try:
                await socket.send_json({"role": "system", "text": "La conexión de chat encontró un error.", "correlation_id": base_correlation_id})
            except Exception as send_exc:
                logger.error("No se pudo notificar al cliente del error: %s", type(send_exc).__name__)
    finally:
        ping_task.cancel()
        if (
            socket.client_state == WebSocketState.CONNECTED
            and socket.application_state == WebSocketState.CONNECTED
        ):
            try:
                await socket.close()
            except RuntimeError:
                logger.debug("WebSocket ya estaba cerrado por el transporte")

