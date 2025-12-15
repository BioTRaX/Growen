# NG-HEADER: Nombre de archivo: telegram_handler.py
# NG-HEADER: Ubicación: services/chat/telegram_handler.py
# NG-HEADER: Descripción: Handler reutilizable para procesar mensajes de Telegram
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Handler reutilizable para procesar mensajes de Telegram."""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from services.chat.price_lookup import extract_product_query

logger = logging.getLogger(__name__)


async def handle_telegram_message(
    text: str,
    chat_id: str,
    db: AsyncSession,
    image_file_id: str | None = None,  # NUEVO: File ID de imagen de Telegram
) -> str:
    """
    Procesa un mensaje de Telegram y retorna la respuesta.
    
    Esta función centraliza la lógica de procesamiento de mensajes para que
    pueda ser reutilizada tanto por el webhook como por el worker de polling.
    
    Args:
        text: Texto del mensaje del usuario (puede estar vacío si solo hay imagen)
        chat_id: ID del chat de Telegram (para logging, no se usa en la respuesta)
        db: Sesión de base de datos asíncrona
        image_file_id: File ID de imagen de Telegram (opcional)
        
    Returns:
        Respuesta generada por el bot (texto limpio, sin prefijos técnicos)
        
    Raises:
        Exception: Si ocurre un error crítico durante el procesamiento
    """
    # Si no hay texto pero hay imagen, usar texto por defecto
    if not text or not text.strip():
        if image_file_id:
            user_text = "¿Qué le pasa a mi planta?"  # Texto por defecto para diagnóstico con imagen
        else:
            return "No recibí ningún mensaje. ¿Podrías escribir algo?"
    else:
        user_text = text.strip()
    
    user_role = "anon"  # Usuarios de Telegram no tienen autenticación
    
    # Si hay imagen, usar flujo de diagnóstico
    if image_file_id:
        try:
            from services.chat.cultivator import diagnose_plant
            
            diagnosis_result = await diagnose_plant(
                user_input=user_text,
                image_file_id=image_file_id,
                conversation_history=None,  # Telegram no tiene historial persistente aún
                session=db,
                user_role=user_role,
            )
            
            # Construir respuesta
            response_parts = [diagnosis_result["diagnosis"]]
            
            if diagnosis_result.get("follow_up_question"):
                response_parts.append(f"\n\n{diagnosis_result['follow_up_question']}")
            
            # Productos recomendados (si hay)
            products = diagnosis_result.get("products", {})
            if any(products.values()):
                response_parts.append("\n\n**Productos recomendados:**")
                for tier_name, tier_products in [
                    ("Gama Baja", products.get("low", [])),
                    ("Gama Media", products.get("medium", [])),
                    ("Gama Alta", products.get("high", [])),
                ]:
                    if tier_products:
                        response_parts.append(f"\n**{tier_name}:**")
                        for prod in tier_products[:3]:
                            price_str = f" - ${prod.get('price', 'N/A')}" if prod.get('price') else ""
                            stock_str = f" (Stock: {prod.get('stock', 0)})" if prod.get('stock', 0) > 0 else " (Sin stock)"
                            tags_str = f" {', '.join(prod.get('tags', []))}" if prod.get('tags') else ""
                            response_parts.append(f"- {prod.get('title', 'N/A')}{price_str}{stock_str}{tags_str}")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"Error en diagnóstico de plantas desde Telegram: {e}", exc_info=True)
            # Fallback a chat general si falla el diagnóstico
            pass  # Continuar al flujo normal
    
    ai_router = AIRouter(core_settings)
    
    # 1. Detectar si es consulta de producto
    product_query = extract_product_query(user_text)
    
    if product_query:
        # Flujo con tool calling para consultas de productos
        try:
            # Buscar contexto relevante en Knowledge Base (RAG) si está disponible
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
                    logger.info(f"RAG: Encontrado contexto para Telegram '{user_text[:50]}...'")
            except Exception as e:
                logger.debug(f"RAG search falló (continuando sin contexto): {e}")
            
            # Construir prompt con contexto RAG si está disponible
            prompt_parts = []
            if rag_context:
                prompt_parts.append(
                    "Contexto relevante de documentación interna:\n"
                    f"{rag_context}\n"
                    "Usa esta información para enriquecer tu respuesta cuando sea relevante."
                )
            prompt_parts.append(f"Usuario: {user_text}")
            prompt_with_context = "\n\n".join(prompt_parts) if prompt_parts else user_text
            
            # Obtener el schema de herramientas para consulta de productos
            provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
            tools_schema = None
            if hasattr(provider, '_build_tools_schema'):
                tools_schema = provider._build_tools_schema(user_role)
            
            # Generar respuesta con tool calling
            answer = await ai_router.run_async(
                task=Task.SHORT_ANSWER.value,
                prompt=prompt_with_context,
                user_context={"role": user_role, "intent": "product_lookup"},
                tools_schema=tools_schema,
            )
            
            # Limpiar prefijo técnico si existe (openai:, ollama:)
            if ":" in answer and answer.split(":")[0] in ("openai", "ollama"):
                answer = answer.split(":", 1)[1].strip()
            
            return answer
            
        except Exception as e:
            logger.error(f"Error procesando consulta de producto en Telegram: {e}", exc_info=True)
            return "Error consultando el producto. Probá más tarde o reformulá tu pregunta."
    
    # 2. Fallback: Chat general sin tools
    try:
        # Buscar contexto RAG para chat general (diagnóstico, etc.)
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
                logger.info(f"RAG: Encontrado contexto para chat general Telegram '{user_text[:50]}...'")
        except Exception as e:
            logger.debug(f"RAG search falló (continuando sin contexto): {e}")
        
        # Construir prompt con contexto RAG si está disponible
        prompt_parts = []
        if rag_context:
            prompt_parts.append(
                "Contexto relevante de documentación interna:\n"
                f"{rag_context}\n"
                "Usa esta información para enriquecer tu respuesta cuando sea relevante."
            )
        prompt_parts.append(f"Usuario: {user_text}")
        prompt_with_context = "\n\n".join(prompt_parts) if prompt_parts else user_text
        
        # Generar respuesta sin tools (chat general)
        raw = await ai_router.run_async(
            task=Task.SHORT_ANSWER.value,
            prompt=prompt_with_context,
            user_context={"role": user_role, "intent": "chat_general"},
        )
        
        # Limpiar prefijo técnico si existe
        if ":" in raw and raw.split(":")[0] in ("openai", "ollama"):
            raw = raw.split(":", 1)[1].strip()
        
        # Separar system prompt si está presente (compatibilidad legacy)
        if "\n\n" in raw:
            reply = raw.split("\n\n")[-1].strip()
        else:
            reply = raw.strip()
        
        return reply
        
    except Exception as e:
        logger.error(f"Error procesando mensaje general en Telegram: {e}", exc_info=True)
        return "Disculpá, hubo un error procesando tu mensaje. Probá más tarde."

