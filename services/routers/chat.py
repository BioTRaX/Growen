# NG-HEADER: Nombre de archivo: chat.py
# NG-HEADER: Ubicacion: services/routers/chat.py
# NG-HEADER: Descripcion: Endpoints y WebSocket para el chat asistido.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Endpoint de chat sincrono que consulta la IA."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError, constr

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from db.session import get_session
from services.auth import SessionData, current_session
from services.chat.memory import (
    MemoryState,
    build_memory_key,
    clear_memory,
    ensure_memory,
    get_memory,
    mark_prompted,
    mark_resolved,
)
# DEPRECATED: La lógica de price_lookup se reemplaza gradualmente por tool-calling vía OpenAI + MCP.
# Mantengo import mínimo solo para tipos y parsing mientras se completa migración.
from services.chat.price_lookup import (
    ProductQuery,
    extract_product_query,
    # log_product_lookup,
    # render_product_response,
    # resolve_product_info,
    # serialize_result,
)
from services.chat.shared import (
    ALLOWED_PRODUCT_INTENT_ROLES,
    ALLOWED_PRODUCT_METRIC_ROLES,
    CLARIFY_CONFIRM_WORDS,
    clarify_prompt_text,
    memory_terms_text,
    normalize_followup_text,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()
from sqlalchemy.ext.asyncio import AsyncSession



class ProductEntryOut(BaseModel):
    name: str
    price: Optional[float] = None
    currency: str
    formatted_price: Optional[str] = None
    source_detail: Optional[str] = None
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    canonical_id: Optional[int] = None
    supplier_item_id: Optional[int] = None
    product_id: Optional[int] = None
    stock_qty: Optional[int] = None
    stock_status: Optional[str] = None
    variant_skus: List[str] = []
    score: Optional[float] = None
    match_reason: Optional[str] = None


class ProductLookupOut(BaseModel):
    status: str
    query: str
    intent: str
    normalized_query: str
    terms: List[str]
    sku_candidates: List[str]
    results: List[ProductEntryOut]
    missing: List[str]
    needs_clarification: Optional[bool] = None
    metrics: Optional[Dict[str, Any]] = None
    took_ms: Optional[int] = None
    errors: List[str] = []


class ChatIn(BaseModel):
    """Modelo del cuerpo recibido en ``POST /chat``."""

    text: constr(min_length=1, max_length=2000)  # type: ignore[name-defined]


class ChatOut(BaseModel):
    """Estructura comun de salida del chat."""

    role: str = "assistant"
    text: str
    type: str = "text"
    data: Optional[ProductLookupOut] = None
    intent: Optional[str] = None
    took_ms: Optional[int] = None


async def _handle_followup(
    *,
    message: str,
    memory_key: str,
    db: AsyncSession,
    memory_state: MemoryState,
    correlation_id: Optional[str],
    include_metrics: bool = False,
) -> Optional[ChatOut]:
    if not memory_state or not memory_state.pending_clarification:
        return None
    normalized = normalize_followup_text(message)
    query = memory_state.query
    if not normalized:
        mark_prompted(memory_key)
        terms = memory_terms_text(query)
        try:
            logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id, "terms": terms})
        except Exception:
            pass
        return ChatOut(text=clarify_prompt_text(terms), type="clarify_prompt", intent="clarify")
    if normalized in CLARIFY_CONFIRM_WORDS:
        # Nuevo flujo simplificado: pedimos al usuario que formule nuevamente la consulta con el SKU o nombre completo.
        mark_resolved(memory_key)
        return ChatOut(
            text="Entendido. Por favor vuelve a pedir el producto indicando el SKU exacto para obtener datos actualizados.",
            type="clarify_ack",
            intent="clarify",
        )
    tokens = normalized.split()
    if len(tokens) <= 3 and not memory_state.prompted:
        mark_prompted(memory_key)
        terms = memory_terms_text(query)
        try:
            logger.info("chat.clarify_prompt", extra={"correlation_id": correlation_id, "terms": terms})
        except Exception:
            pass
        return ChatOut(text=clarify_prompt_text(terms), type="clarify_prompt", intent="clarify")
    return None


@router.post("/chat", response_model=ChatOut)
async def chat_endpoint(
    payload: ChatIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    """Resuelve intents controlados y delega al router de IA como fallback."""

    correlation_id = getattr(request.state, "correlation_id", None) or request.headers.get("x-correlation-id")
    session_id = session_data.session.id if session_data.session else None
    host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    memory_key = build_memory_key(session_id=session_id, role=session_data.role, host=host, user_agent=user_agent)
    memory_state = get_memory(memory_key)

    product_query = extract_product_query(payload.text)
    if product_query and session_data.role in ALLOWED_PRODUCT_INTENT_ROLES:
        # Nuevo flujo: delegar a tool-calling (OpenAI -> MCP) sin price_lookup detallado local.
        ai_router = AIRouter(core_settings)
        provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
        chat_with_tools = getattr(provider, "chat_with_tools", None)
        if chat_with_tools:
            try:
                answer = await chat_with_tools(prompt=payload.text, user_role=session_data.role)
                return ChatOut(text=answer, intent="product_tool")
            except Exception:
                logger.exception("chat.tool_call_error")
                return ChatOut(text="Error temporal consultando información de producto.")
        return ChatOut(text="Necesitas una cuenta autorizada para consultar precios y stock.", intent="forbidden")

    if memory_state:
        follow = await _handle_followup(
            message=payload.text,
            memory_key=memory_key,
            db=db,
            memory_state=memory_state,
            correlation_id=correlation_id,
        )
        if follow is not None:
            return follow
        if not memory_state.pending_clarification:
            clear_memory(memory_key)

    ai_router = AIRouter(core_settings)
    raw = ai_router.run(Task.SHORT_ANSWER.value, payload.text)
    # Extrae ultimo bloque luego de doble newline si existe (ayuda a descartar prefijos del modelo)
    separator = "\n\n"
    if separator in raw:
        reply = raw.split(separator)[-1].strip()
    else:
        reply = raw.strip()
    try:
        from agent_core.config import settings as _settings

        if _settings.env == "dev":
            words = [w.strip("?!.,;:") for w in payload.text.split() if len(w.strip("?!.,;:")) >= 3]
            if words and not any(w in reply for w in words):
                reply = payload.text
    except Exception:
        pass
    try:
        logger.info("chat.ai_fallback", extra={"correlation_id": correlation_id})
    except Exception:
        pass
    return ChatOut(text=reply)


