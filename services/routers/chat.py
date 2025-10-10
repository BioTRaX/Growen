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

from ai.intent_classifier import classify_intent, UserIntent
from services.chat.sales_handler.tools import manejar_conversacion_venta, consultar_producto


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


@router.post("/chat", response_model=ChatOut)
async def chat_endpoint(
    payload: ChatIn,
    request: Request,
    session_data: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    """Clasifica la intención del usuario y enruta al manejador correspondiente."""
    ai_router = AIRouter(core_settings)
    user_text = payload.text
    user_role = session_data.role

    # 1. Clasificar la intención del usuario
    intent = await classify_intent(ai_router, user_text)

    # 2. Obtener o inicializar la memoria de la conversación
    memory_key = build_memory_key(session_id=session_data.session.id, role=user_role)
    conversation_state = get_memory(memory_key) or {}

    # 3. Enrutar según la intención
    if intent == UserIntent.VENTA_CONVERSACIONAL:
        sales_state = conversation_state.get("sales_flow", None)
        
        entrada_para_venta = user_text
        if not (sales_state and sales_state.get("fase") != "INICIO"):
            partes = user_text.lower().split()
            if partes and partes[0] in ["vende", "registra", "factura", "anota"]:
                entrada_para_venta = " ".join(partes)

        result = await manejar_conversacion_venta(entrada_para_venta, sales_state, user_role)
        
        conversation_state["sales_flow"] = result["nuevo_estado"]
        ensure_memory(memory_key, conversation_state)
        
        return ChatOut(text=result["respuesta_para_usuario"], intent=UserIntent.VENTA_CONVERSACIONAL.value)

    elif intent == UserIntent.CONSULTA_PRECIO:
        palabras_clave = ["precio de", "cuánto cuesta", "valor de", "stock de", "hay de"]
        nombre_producto = user_text
        for palabra in palabras_clave:
            if palabra in user_text.lower():
                nombre_producto = user_text.lower().split(palabra)[1].strip()
                break
        
        respuesta_producto = await consultar_producto(nombre_producto, user_role)
        return ChatOut(text=respuesta_producto, intent=UserIntent.CONSULTA_PRECIO.value)

    # Fallback para CHAT_GENERAL o UNKNOWN
    else:
        raw = ai_router.run(Task.SHORT_ANSWER.value, user_text)
        separator = "\n\n"
        if separator in raw:
            reply = raw.split(separator)[-1].strip()
        else:
            reply = raw.strip()
        return ChatOut(text=reply, intent=UserIntent.CHAT_GENERAL.value)