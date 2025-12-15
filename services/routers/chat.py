# NG-HEADER: Nombre de archivo: chat.py
# NG-HEADER: Ubicacion: services/routers/chat.py
# NG-HEADER: Descripcion: Endpoints y WebSocket para el chat asistido.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Endpoint de chat asíncrono que consulta la IA mediante AIRouter.

El flujo principal es:
1. Clasificar intención del usuario (classify_intent).
2. Gestionar memoria de conversación para aclaraciones.
3. Si es consulta de producto: run_async con contexto de usuario.
4. Si es venta conversacional: manejar_conversacion_venta.
5. Fallback: chat general vía run_async.

El AIRouter abstrae la selección de proveedor (OpenAI/Ollama) y el manejo
de tools, simplificando este endpoint a: detección → router → respuesta.

Nota Etapa 0: Durante la transición, la variable de entorno 
CHAT_USE_LLM_FOR_PRODUCTS controla si usamos LLM (con tool calling) o
el fallback local para consultas de producto. Por defecto, usa fallback local
para mantener compatibilidad con tests legacy.
"""

from __future__ import annotations

import logging
import os
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
    resolve_price,
    serialize_result,
    render_product_response,
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

from ai.intent_classifier import classify_intent, UserIntent
from services.chat.sales_handler.tools import manejar_conversacion_venta, consultar_producto
from services.chat.history import save_message, get_recent_history

logger = logging.getLogger(__name__)

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
    # Etapa 1: Campos de enriquecimiento estructurado
    technical_specs: Optional[Dict[str, Any]] = None
    usage_instructions: Optional[Dict[str, Any]] = None


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
    image_file_id: Optional[str] = None  # File ID de Telegram (opcional)
    image_url: Optional[str] = None  # URL pública de imagen (opcional, alternativa a file_id)


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

    # 0. Generar session_id estable para historial conversacional
    # Usar session.id si existe, sino construir con host+user_agent (fallback para guests)
    try:
        chat_session_id = session_data.session.id if getattr(session_data, "session", None) else None
    except Exception:
        chat_session_id = None
    
    if not chat_session_id:
        # Fallback: generar ID basado en IP + user agent (menos robusto pero funcional para MVP)
        host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        import hashlib
        chat_session_id = hashlib.md5(f"{host}_{user_agent}".encode()).hexdigest()[:16]
    
    # 0.1 Recuperar historial reciente para memoria conversacional
    history_context = await get_recent_history(db, chat_session_id, limit=6)

    # 1. Clasificar la intención del usuario
    # Si hay imagen, forzar intención DIAGNOSTICO
    if payload.image_file_id or payload.image_url:
        intent = UserIntent.DIAGNOSTICO
    else:
        intent = await classify_intent(ai_router, user_text)

    # 2. Obtener o inicializar la memoria de la conversación (robusto ante sesión ausente)
    try:
        sid = session_data.session.id if getattr(session_data, "session", None) else None
    except Exception:
        sid = None
    host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    memory_key = build_memory_key(session_id=sid, role=user_role, host=host, user_agent=user_agent)
    # Nota: la memoria estructurada (MemoryState) no es compatible con el flujo de ventas conversacionales actual.
    # Para evitar errores de tipo, usamos un dict local transitorio cuando corresponde.
    conversation_state: Dict[str, Any] = {}

    # 3. Primero, gestionar flujo de aclaración si hay memoria pendiente
    memory_state = get_memory(memory_key)
    if memory_state and memory_state.pending_clarification:
        normalized = normalize_followup_text(user_text)
        if not normalized:
            mark_prompted(memory_key)
            terms = memory_terms_text(memory_state.query)
            return ChatOut(text=clarify_prompt_text(terms), type="clarify_prompt", intent="clarify")
        if normalized in CLARIFY_CONFIRM_WORDS:
            include_metrics = user_role in ALLOWED_PRODUCT_METRIC_ROLES
            try:
                # Re-ejecutar la resolución usando la consulta previa almacenada
                prior_query_text = memory_state.query.raw_text
                result = await resolve_price(prior_query_text, db, limit=5)
                payload = serialize_result(result, include_metrics=include_metrics)
                text = render_product_response(result)
                clear_memory(memory_key)
                return ChatOut(text=text, type="product_answer", intent=result.intent, data=payload, took_ms=payload.get("took_ms"))
            except Exception:
                logger.exception("chat.local_price_confirm_error")
                clear_memory(memory_key)
                return ChatOut(text="Error resolviendo información de producto.", type="error", intent="clarify")
        tokens = normalized.split()
        if len(tokens) <= 3 and not memory_state.prompted:
            mark_prompted(memory_key)
            terms = memory_terms_text(memory_state.query)
            return ChatOut(text=clarify_prompt_text(terms), type="clarify_prompt", intent="clarify")

    # 4. Detección de consultas de producto (precio/stock) con tool calling asíncrono
    #    El AIRouter maneja internamente el tool calling con OpenAI.
    product_query = extract_product_query(user_text)
    if product_query or intent == UserIntent.CONSULTA_PRECIO:
        # Flujo principal: usar run_async con el LLM (OpenAI + tool calling)
        try:
            # Buscar contexto relevante en Knowledge Base (RAG)
            rag_context = ""
            try:
                from services.rag.search import get_rag_search_service
                rag_service = get_rag_search_service()
                rag_context = await rag_service.search_and_format_context(
                    query=user_text,
                    session=db,
                    top_k=3,
                    min_similarity=0.5
                )
                if rag_context:
                    logger.info(f"RAG: Encontrado contexto para '{user_text[:50]}...'")
            except Exception as e:
                logger.debug(f"RAG search falló (continuando sin contexto): {e}")
            
            # Construir prompt con historial conversacional + contexto RAG
            prompt_parts = []
            if history_context:
                prompt_parts.append(history_context)
            if rag_context:
                prompt_parts.append(
                    "Contexto relevante de documentación interna:\n"
                    f"{rag_context}\n"
                    "Usa esta información para enriquecer tu respuesta cuando sea relevante."
                )
            prompt_parts.append(f"Usuario: {user_text}")
            prompt_with_history = "\n\n".join(prompt_parts)
            
            # Obtener el schema de herramientas para consulta de productos
            # El provider OpenAI construye el schema basado en el rol del usuario
            provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
            tools_schema = None
            if hasattr(provider, '_build_tools_schema'):
                tools_schema = provider._build_tools_schema(user_role)
            
            answer = await ai_router.run_async(
                task=Task.SHORT_ANSWER.value,
                prompt=prompt_with_history,
                user_context={"role": user_role, "intent": "product_lookup"},
                tools_schema=tools_schema,
            )
            
            # Limpiar prefijo técnico si existe (openai:, ollama:)
            if ":" in answer and answer.split(":")[0] in ("openai", "ollama"):
                answer = answer.split(":", 1)[1].strip()
            
            # Guardar mensajes en historial (con metadata de tools si está disponible)
            try:
                logger.info(f"Guardando mensaje user en session {chat_session_id[:8]}...")
                await save_message(
                    db, 
                    chat_session_id, 
                    "user", 
                    user_text, 
                    metadata={
                        "intent": intent.value if hasattr(intent, 'value') else str(intent),
                        "used_rag": bool(rag_context),
                    }
                )
                
                # Intentar obtener información de tools usadas desde el provider
                tools_metadata = {}
                try:
                    if hasattr(provider, '_last_tool_calls'):
                        tools_metadata = {
                            "tools_used": provider._last_tool_calls,
                            "tools_count": len(provider._last_tool_calls) if provider._last_tool_calls else 0,
                        }
                except Exception:
                    pass
                
                logger.info(f"Guardando mensaje assistant en session {chat_session_id[:8]}...")
                await save_message(
                    db, 
                    chat_session_id, 
                    "assistant", 
                    answer, 
                    metadata={
                        "type": "product_answer",
                        "used_rag": bool(rag_context),
                        **tools_metadata,
                    }
                )
                logger.info(f"Commit de mensajes para session {chat_session_id[:8]}...")
                await db.commit()
                logger.info(f"✓ Mensajes guardados exitosamente para session {chat_session_id[:8]}")
            except Exception as e:
                logger.error(f"Error guardando mensajes: {type(e).__name__}: {e}")
                # No fallar el request, continuar con la respuesta
            
            # Retornar respuesta del LLM
            clear_memory(memory_key)
            return ChatOut(text=answer, type="product_answer", intent="product_tool")
                
        except Exception as e:
            # Si falla el LLM, usar fallback local
            logger.warning("chat.run_async_error: %s, usando fallback local", e)

        # Fallback: resolución local legacy (mantener mientras se completa migración)
        include_metrics = user_role in ALLOWED_PRODUCT_METRIC_ROLES
        try:
            result = await resolve_price(user_text, db, limit=5)
            payload = serialize_result(result, include_metrics=include_metrics)
            text = render_product_response(result)
            # Si hay ambigüedad, almacenamos memoria para el flujo de aclaración
            if payload.get("needs_clarification"):
                ensure_memory(memory_key, result.query, pending=True, rendered=text)
            else:
                clear_memory(memory_key)
            return ChatOut(text=text, type="product_answer", intent=result.intent, data=payload, took_ms=payload.get("took_ms"))
        except Exception:
            logger.exception("chat.local_price_fallback_error")
            return ChatOut(text="Error resolviendo información de producto.", type="error", intent=UserIntent.CONSULTA_PRECIO.value)

    # 5. Diagnóstico de plantas (Modo Cultivador)
    if intent == UserIntent.DIAGNOSTICO:
        try:
            from services.chat.cultivator import diagnose_plant
            
            # Obtener historial reciente para contexto
            conversation_history = await get_recent_history(db, chat_session_id, limit=10)
            
            # Llamar a diagnose_plant
            diagnosis_result = await diagnose_plant(
                user_input=user_text,
                image_file_id=payload.image_file_id,
                image_url=payload.image_url,
                conversation_history=conversation_history,
                session=db,
                user_role=user_role,
            )
            
            # Construir respuesta con diagnóstico y productos recomendados
            response_parts = [diagnosis_result["diagnosis"]]
            
            # Si hay pregunta de seguimiento, agregarla
            if diagnosis_result.get("follow_up_question"):
                response_parts.append(f"\n\n{diagnosis_result['follow_up_question']}")
            
            # Si hay productos recomendados, agregarlos
            products = diagnosis_result.get("products", {})
            if any(products.values()):  # Si hay productos en alguna gama
                response_parts.append("\n\n**Productos recomendados:**")
                
                for tier_name, tier_products in [
                    ("Gama Baja", products.get("low", [])),
                    ("Gama Media", products.get("medium", [])),
                    ("Gama Alta", products.get("high", [])),
                ]:
                    if tier_products:
                        response_parts.append(f"\n**{tier_name}:**")
                        for prod in tier_products[:3]:  # Máximo 3 por gama
                            price_str = f" - ${prod.get('price', 'N/A')}" if prod.get('price') else ""
                            stock_str = f" (Stock: {prod.get('stock', 0)})" if prod.get('stock', 0) > 0 else " (Sin stock)"
                            tags_str = f" {', '.join(prod.get('tags', []))}" if prod.get('tags') else ""
                            response_parts.append(f"- {prod.get('title', 'N/A')}{price_str}{stock_str}{tags_str}")
            
            answer = "\n".join(response_parts)
            
            # Guardar mensajes en historial
            await save_message(
                db, 
                chat_session_id, 
                "user", 
                user_text, 
                metadata={
                    "intent": intent.value if hasattr(intent, 'value') else str(intent),
                    "has_image": bool(payload.image_file_id or payload.image_url),
                    "image_file_id": payload.image_file_id,
                    "image_url": payload.image_url,
                }
            )
            await save_message(
                db, 
                chat_session_id, 
                "assistant", 
                answer, 
                metadata={
                    "type": "diagnosis",
                    "confidence": diagnosis_result.get("confidence", 0.7),
                    "has_rag_context": bool(diagnosis_result.get("rag_context")),
                }
            )
            await db.commit()
            
            return ChatOut(text=answer, type="diagnosis", intent=UserIntent.DIAGNOSTICO.value)
            
        except Exception as e:
            logger.error(f"Error en diagnóstico de plantas: {e}", exc_info=True)
            # Fallback a chat general si falla el diagnóstico
            pass  # Continuar al flujo de chat general
    
    # 6. Ventas conversacionales (si no aplicó consulta de producto ni diagnóstico)
    if intent == UserIntent.VENTA_CONVERSACIONAL:
        sales_state = conversation_state.get("sales_flow", None)
        entrada_para_venta = user_text
        if not (sales_state and sales_state.get("fase") != "INICIO"):
            partes = user_text.lower().split()
            if partes and partes[0] in ["vende", "registra", "factura", "anota"]:
                entrada_para_venta = " ".join(partes)
        result = await manejar_conversacion_venta(entrada_para_venta, sales_state, user_role)
        conversation_state["sales_flow"] = result.get("nuevo_estado")
        
        # Guardar mensajes en historial
        await save_message(db, chat_session_id, "user", user_text, metadata={"intent": intent.value if hasattr(intent, 'value') else str(intent)})
        await save_message(db, chat_session_id, "assistant", result["respuesta_para_usuario"], metadata={"type": "sales_conversation"})
        await db.commit()
        
        return ChatOut(text=result["respuesta_para_usuario"], intent=UserIntent.VENTA_CONVERSACIONAL.value)

    # 7. Fallback: Chat general con contexto de usuario
    else:
        # Usar run_async para chat general, pasando el contexto del usuario
        # El chatbot puede necesitar saber si habla con Admin/Colaborador vs Cliente
        
        # Buscar contexto relevante en Knowledge Base (RAG) para chat general
        rag_context = ""
        try:
            from services.rag.search import get_rag_search_service
            rag_service = get_rag_search_service()
            rag_context = await rag_service.search_and_format_context(
                query=user_text,
                session=db,
                top_k=3,
                min_similarity=0.5
            )
            if rag_context:
                logger.info(f"RAG: Encontrado contexto para chat general '{user_text[:50]}...'")
        except Exception as e:
            logger.debug(f"RAG search falló (continuando sin contexto): {e}")
        
        # Construir prompt con historial conversacional + contexto RAG
        prompt_parts = []
        if history_context:
            prompt_parts.append(history_context)
        if rag_context:
            prompt_parts.append(
                "Contexto relevante de documentación interna:\n"
                f"{rag_context}\n"
                "Usa esta información para enriquecer tu respuesta cuando sea relevante."
            )
        prompt_parts.append(f"Usuario: {user_text}")
        prompt_with_history = "\n\n".join(prompt_parts) if prompt_parts else user_text
        
        raw = await ai_router.run_async(
            task=Task.SHORT_ANSWER.value,
            prompt=prompt_with_history,
            user_context={"role": user_role, "intent": "chat_general"},
        )
        
        # Limpiar prefijo técnico si existe
        if ":" in raw and raw.split(":")[0] in ("openai", "ollama"):
            raw = raw.split(":", 1)[1].strip()
        
        # Separar system prompt si está presente (compatibilidad legacy)
        separator = "\n\n"
        if separator in raw:
            reply = raw.split(separator)[-1].strip()
        else:
            reply = raw.strip()
        
        # Guardar mensajes en historial
        await save_message(db, chat_session_id, "user", user_text, metadata={"intent": intent.value if hasattr(intent, 'value') else str(intent)})
        await save_message(db, chat_session_id, "assistant", reply, metadata={"type": "chat_general"})
        await db.commit()
        
        return ChatOut(text=reply, intent=UserIntent.CHAT_GENERAL.value)