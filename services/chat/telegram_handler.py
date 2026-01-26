# NG-HEADER: Nombre de archivo: telegram_handler.py
# NG-HEADER: Ubicación: services/chat/telegram_handler.py
# NG-HEADER: Descripción: Handler reutilizable para procesar mensajes de Telegram
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Handler reutilizable para procesar mensajes de Telegram."""

from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from services.chat.price_lookup import extract_product_query
from services.chat.history import save_message, get_recent_history

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
    
    # Construir session_id estable para Telegram
    telegram_session_id = f"telegram:{chat_id}"
    
    # Recuperar historial reciente para contexto
    try:
        logger.debug(f"Recuperando historial para session_id={telegram_session_id}")
        history_context = await get_recent_history(db, telegram_session_id, limit=6)
        logger.debug(f"Historial recuperado: {len(history_context) if history_context else 0} caracteres")
    except Exception as e:
        logger.debug(f"Error recuperando historial para Telegram: {e}")
        history_context = ""
    
    # Detectar si hay un diagnóstico en curso basándose en el historial
    # Esto permite mantener el modo CULTIVATOR incluso si el mensaje actual no tiene imagen
    conversation_state = None
    logger.debug(f"Analizando historial para detectar conversación en curso...")
    if history_context:
        history_lower = history_context.lower()
        diagnostic_indicators = [
            "hojas amarillas", "clorosis", "diagnóstico", "diagnosticar",
            "carencia", "deficiencia", "planta", "cultivo", "ph",
            "vegetativo", "floración", "síntomas", "problema",
            "hidropónico", "hidroponica", "dwc", "sustrato",
            "fertilizante", "nutrientes", "qué le pasa",
        ]
        is_diagnosis_in_progress = any(indicator in history_lower for indicator in diagnostic_indicators)
        if is_diagnosis_in_progress:
            conversation_state = {"current_mode": "CULTIVATOR"}
            logger.debug(f"Conversación de diagnóstico detectada en historial")
    
    logger.debug(f"Estado de conversación: {conversation_state}")
    
    # Determinar modo y tarea según el contexto
    mode = None
    task = Task.SHORT_ANSWER
    
    logger.debug(f"Determinando modo... image_file_id={image_file_id}, conversation_state={conversation_state}")
    
    if image_file_id or (conversation_state and conversation_state.get("current_mode") == "CULTIVATOR"):
        mode = "CULTIVATOR"
        task = Task.LONG_ANSWER
        logger.debug(f"Modo CULTIVATOR seleccionado (imagen o diagnóstico en curso)")
    else:
        logger.debug(f"Verificando si es consulta de producto...")
        # Detectar si es una consulta de producto
        product_query_result = extract_product_query(user_text)
        logger.debug(f"Resultado de extract_product_query: {product_query_result}")
        if product_query_result:
            mode = "PRODUCT_LOOKUP"
            task = Task.SHORT_ANSWER
            logger.debug(f"Modo PRODUCT_LOOKUP seleccionado")
    
    logger.debug(f"Modo final: {mode}, Tarea final: {task}")

    # Si hay imagen, usar flujo de diagnóstico
    if image_file_id:
        try:
            from services.chat.cultivator import diagnose_plant
            
            diagnosis_result = await diagnose_plant(
                user_input=user_text,
                image_file_id=image_file_id,
                conversation_history=history_context if history_context else None,
                session=db,
                user_role=user_role,
            )
            
            # Guardar mensaje del usuario y respuesta
            try:
                await save_message(
                    db, telegram_session_id, "user", user_text,
                    metadata={"intent": "diagnostico", "image_file_id": image_file_id}
                )
                await save_message(
                    db, telegram_session_id, "assistant", diagnosis_result["diagnosis"],
                    metadata={"type": "diagnostico"}
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Error guardando mensajes de Telegram: {e}", exc_info=True)
                await db.rollback()
            
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
            
            # Construir prompt con historial conversacional + contexto RAG si está disponible
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
            prompt_with_context = "\n\n".join(prompt_parts) if prompt_parts else user_text
            
            # Obtener el schema de herramientas para consulta de productos
            provider = ai_router.get_provider(Task.SHORT_ANSWER.value)
            tools_schema = None
            if hasattr(provider, '_build_tools_schema'):
                tools_schema = provider._build_tools_schema(user_role)
            
            logger.debug(f"Preparando llamada a AIRouter con task={Task.SHORT_ANSWER.value}, intent=product_lookup")
            
            # Generar respuesta con tool calling
            try:
                logger.debug(f"Llamando a ai_router.run_async para consulta de producto...")
                answer = await ai_router.run_async(
                    task=Task.SHORT_ANSWER.value,
                    prompt=prompt_with_context,
                    user_context={"role": user_role, "intent": "product_lookup"},
                    tools_schema=tools_schema,
                )
                logger.debug(f"Respuesta de ai_router.run_async recibida.")
            except Exception as e:
                logger.error(f"Error durante la llamada a ai_router.run_async para producto: {e}", exc_info=True)
                raise # Re-lanzar para que el except externo lo capture
            
            # Limpiar prefijo técnico si existe (openai:, ollama:)
            if ":" in answer and answer.split(":")[0] in ("openai", "ollama"):
                answer = answer.split(":", 1)[1].strip()
            
            # Detectar y procesar envío de imágenes
            # Soporta: [SEND_IMAGE: path] y Markdown ![alt](path)
            import re
            
            # Estrategia 1: Tags explícitos [SEND_IMAGE: ...]
            image_matches = re.findall(r'\[SEND_IMAGE: (.*?)\]', answer)
            
            # Estrategia 2: Markdown images ![alt](url) - Fallback si el modelo ignora instrucciones
            markdown_matches = re.findall(r'!\[.*?\]\((.*?)\)', answer)
            
            # Unificar y procesar
            all_images = list(image_matches) + list(markdown_matches)
            
            for image_path in all_images:
                raw_path = image_path.strip()
                
                # Limpiar tags de la respuesta visible
                answer = answer.replace(f"[SEND_IMAGE: {raw_path}]", "")
                # Limpiar markdown de la respuesta visible (opcional, pero mejor UX)
                # Regex más complejo para reemplazar exactamente el markdown correcto con el path
                answer = re.sub(r'!\[.*?\]\(' + re.escape(raw_path) + r'\)', '', answer)

                # Lógica de saneamiento de URL alucinada por el LLM (hack para nicegrow.com)
                clean_path = raw_path
                if "nicegrow.com/media/" in raw_path:
                    clean_path = raw_path.split("nicegrow.com/")[-1].lstrip("/")
                elif raw_path.startswith("/media/"):
                    clean_path = raw_path.lstrip("/")

                # Convertir paths relativos a absolutos desde el root del proyecto
                from pathlib import Path as PathLib
                ROOT = PathLib(__file__).resolve().parent.parent.parent
                
                # Normalizar separadores primero (Windows usa \, queremos /)
                clean_path = clean_path.replace("\\", "/")
                
                if clean_path.startswith("media/"):
                    # Path tiene media/ prefix - convertir a Devs/Imagenes/
                    clean_path = clean_path.replace("media/", "Devs/Imagenes/", 1)
                    clean_path = str(ROOT / clean_path)
                elif clean_path.startswith("Productos/") or "/Productos/" in clean_path:
                    # Path de producto sin prefix - agregar Devs/Imagenes/
                    clean_path = str(ROOT / "Devs" / "Imagenes" / clean_path)
                elif not clean_path.startswith(("c:", "C:", "/")):
                    # Otros paths relativos - intentar con Devs/Imagenes/
                    candidate = ROOT / "Devs" / "Imagenes" / clean_path
                    if candidate.exists():
                        clean_path = str(candidate)

                
                # Optimización WebP: Buscar versión optimizada en 'derived'
                # Estructura típica: .../Productos/12/raw/FILE -> .../Productos/12/derived/*-full.webp
                try:
                    logger.debug(f"Iniciando optimización WebP para: {clean_path}")
                    p = Path(clean_path)
                    logger.debug(f"Path creado, verificando existencia...")
                    if p.exists() and "raw" in p.parts:
                        logger.debug(f"Path existe y contiene 'raw', buscando derived...")
                        # Identificar carpeta 'derived' paralela a 'raw'
                        parent = p.parent.parent # ej: .../Productos/12
                        derived_dir = parent / "derived"
                        logger.debug(f"Buscando en derived_dir: {derived_dir}")
                        if derived_dir.exists():
                            logger.debug(f"Derived dir existe, buscando archivos webp...")
                            # Buscar archivos webp, preferiblemente 'card' o 'full'
                            webp_candidates = list(derived_dir.glob("*.webp"))
                            logger.debug(f"Encontrados {len(webp_candidates)} archivos webp")
                            if webp_candidates:
                                # Priorizar 'card' > 'full' > cualquiera (card es más liviano para Telegram)
                                chosen = None
                                for cand in webp_candidates:
                                    if "-card.webp" in cand.name:
                                        chosen = cand
                                        break
                                if not chosen:
                                    for cand in webp_candidates:
                                        if "-full.webp" in cand.name:
                                            chosen = cand
                                            break
                                if not chosen and webp_candidates:
                                    chosen = webp_candidates[0]
                                
                                if chosen:
                                    logger.info(f"Optimización: Usando WebP {chosen} en lugar de RAW {p}")
                                    clean_path = str(chosen)
                                else:
                                    logger.debug(f"No se encontró archivo webp preferido, usando path original")
                    else:
                        logger.debug(f"Path no existe o no contiene 'raw': exists={p.exists()}, parts={p.parts}")
                except Exception as e:
                    logger.error(f"Error intentando optimizar imagen a WebP: {e}", exc_info=True)

                logger.debug(f"Intentando enviar imagen: {clean_path}")
                try:
                    from services.notifications.telegram import send_photo
                    # Enviar la imagen
                    await send_photo(photo=clean_path, chat_id=chat_id)
                    logger.info(f"✓ Imagen enviada a Telegram: {clean_path} (raw: {raw_path})")
                except Exception as e:
                    logger.error(f"✗ Error enviando imagen {clean_path}: {e}", exc_info=True)
            
            answer = answer.strip()

            # Guardar mensaje del usuario y respuesta
            try:
                await save_message(
                    db, telegram_session_id, "user", user_text,
                    metadata={"intent": "product_lookup"}
                )
                await save_message(
                    db, telegram_session_id, "assistant", answer,
                    metadata={"type": "product_answer"}
                )
                await db.commit()
            except Exception as e:
                logger.error(f"Error guardando mensajes de Telegram: {e}", exc_info=True)
                await db.rollback()
            
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
        
        # Construir prompt con historial conversacional + contexto RAG si está disponible
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
        prompt_with_context = "\n\n".join(prompt_parts) if prompt_parts else user_text
        
        # Generar respuesta sin tools (chat general o continuación de diagnóstico)
        # Si hay diagnóstico en curso, usar intent DIAGNOSTICO para activar persona CULTIVATOR
        active_intent = "DIAGNOSTICO" if conversation_state else "chat_general"
        raw = await ai_router.run_async(
            task=Task.SHORT_ANSWER.value,
            prompt=prompt_with_context,
            user_context={
                "role": user_role, 
                "intent": active_intent,
                "conversation_state": conversation_state,  # Mantener modo CULTIVATOR si aplica
            },
        )
        
        # Limpiar prefijo técnico si existe
        if ":" in raw and raw.split(":")[0] in ("openai", "ollama"):
            raw = raw.split(":", 1)[1].strip()
        
        # Separar system prompt si está presente (compatibilidad legacy)
        if "\n\n" in raw:
            reply = raw.split("\n\n")[-1].strip()
        else:
            reply = raw.strip()
        
        # Guardar mensaje del usuario y respuesta
        try:
            await save_message(
                db, telegram_session_id, "user", user_text,
                metadata={"intent": "chat_general"}
            )
            await save_message(
                db, telegram_session_id, "assistant", reply,
                metadata={"type": "chat_general"}
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Error guardando mensajes de Telegram: {e}", exc_info=True)
            await db.rollback()
        
        return reply
        
    except Exception as e:
        logger.error(f"Error procesando mensaje general en Telegram: {e}", exc_info=True)
        return "Disculpá, hubo un error procesando tu mensaje. Probá más tarde."

