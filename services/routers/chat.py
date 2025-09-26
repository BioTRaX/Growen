# NG-HEADER: Nombre de archivo: chat.py
# NG-HEADER: Ubicacion: services/routers/chat.py
# NG-HEADER: Descripcion: Endpoints y WebSocket para el chat asistido.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Endpoint de chat sincrono que consulta la IA."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError, constr

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from db.session import get_session
from services.auth import SessionData, current_session
from services.chat.memory import (
    build_memory_key,
    clear_memory,
    ensure_memory,
    get_memory,
    mark_prompted,
    mark_resolved,
)
from services.chat.price_lookup import (
    ProductQuery,
    extract_product_query,
    log_product_lookup,
    render_product_response,
    resolve_product_info,
    serialize_result,
)
from sqlalchemy.ext.asyncio import AsyncSession

ALLOWED_PRODUCT_INTENT_ROLES = {"admin", "colaborador", "cliente"}

CLARIFY_CONFIRM_WORDS = {
    "si",
    "si",
    "dale",
    "ok",
    "okay",
    "vale",
    "mostrar",
    "mostrame",
    "mostra",
    "mostralo",
    "mostrarlo",
    "precios",
    "precio",
    "stock",
    "dale si",
}

router = APIRouter()


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


def _normalize_followup_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = ascii_text.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _clarify_text(memory_terms: str) -> str:
    focus = memory_terms or "la consulta"
    return f"Seguimos con {focus}. Queres que te muestre precios y stock?"


def _memory_terms(query: ProductQuery) -> str:
    if query.terms:
        return " ".join(query.terms)
    if query.normalized_text:
        return query.normalized_text
    return query.raw_text


async def _handle_followup(
    *,
    message: str,
    memory_key: str,
    db: AsyncSession,
    memory_state,
) -> Optional[ChatOut]:
    if not memory_state or not memory_state.pending_clarification:
        return None
    normalized = _normalize_followup_text(message)
    query = memory_state.query
    if not normalized:
        mark_prompted(memory_key)
        terms = _memory_terms(query)
        return ChatOut(text=_clarify_text(terms), type="clarify_prompt", intent="clarify")
    if normalized in CLARIFY_CONFIRM_WORDS:
        result = await resolve_product_info(query, db)
        rendered = render_product_response(result)
        serialized = serialize_result(result)
        try:
            payload = ProductLookupOut.model_validate(serialized)
        except ValidationError:
            payload = ProductLookupOut(**serialized)  # type: ignore[arg-type]
        ensure_memory(memory_key, query, pending=result.status == "ambiguous", rendered=rendered)
        if result.status != "ambiguous":
            mark_resolved(memory_key)
        return ChatOut(
            text=rendered,
            type="product_answer",
            data=payload,
            intent=result.intent,
            took_ms=result.took_ms,
        )
    tokens = normalized.split()
    if len(tokens) <= 3 and not memory_state.prompted:
        mark_prompted(memory_key)
        terms = _memory_terms(query)
        return ChatOut(text=_clarify_text(terms), type="clarify_prompt", intent="clarify")
    return None


@router.post("/chat", response_model=ChatOut)
async def chat_endpoint(
    payload: ChatIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    """Resuelve intents controlados y delega al router de IA como fallback."""

    session_id = session_data.session.id if session_data.session else None
    host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    memory_key = build_memory_key(session_id=session_id, role=session_data.role, host=host, user_agent=user_agent)
    memory_state = get_memory(memory_key)

    product_query = extract_product_query(payload.text)
    if product_query:
        if session_data.role not in ALLOWED_PRODUCT_INTENT_ROLES:
            return ChatOut(
                text="Necesitas una cuenta autorizada para consultar precios y stock.",
                intent="forbidden",
            )

        if (
            memory_state
            and memory_state.pending_clarification
            and not product_query.explicit_price
            and not product_query.explicit_stock
            and not memory_state.prompted
        ):
            mark_prompted(memory_key)
            terms = _memory_terms(memory_state.query)
            return ChatOut(text=_clarify_text(terms), type="clarify_prompt", intent="clarify")

        result = await resolve_product_info(product_query, db)
        rendered = render_product_response(result)
        serialized = serialize_result(result)
        try:
            payload_out = ProductLookupOut.model_validate(serialized)
        except ValidationError:
            payload_out = ProductLookupOut(**serialized)  # type: ignore[arg-type]

        ensure_memory(
            memory_key,
            product_query,
            pending=result.status == "ambiguous",
            rendered=rendered,
        )
        if result.status != "ambiguous":
            mark_resolved(memory_key)

        await log_product_lookup(
            db,
            user_id=session_data.user.id if session_data.user else None,
            ip=request.client.host if request.client else None,
            original_text=payload.text,
            product_query=product_query,
            result=result,
        )

        return ChatOut(
            text=rendered,
            type="product_answer",
            data=payload_out,
            intent=result.intent,
            took_ms=result.took_ms,
        )

    if memory_state:
        follow = await _handle_followup(
            message=payload.text,
            memory_key=memory_key,
            db=db,
            memory_state=memory_state,
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
    return ChatOut(text=reply)
