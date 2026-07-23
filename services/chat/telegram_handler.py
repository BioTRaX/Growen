# NG-HEADER: Nombre de archivo: telegram_handler.py
# NG-HEADER: Ubicación: services/chat/telegram_handler.py
# NG-HEADER: Descripción: Handler reutilizable para procesar mensajes de Telegram
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Handler reutilizable para procesar mensajes de Telegram."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task
from services.chat.price_lookup import extract_product_query
from services.chat.history import get_or_create_session, save_message, get_recent_history
from services.chat.external_identity import consume_link_code, opaque_conversation_key, resolve_identity, revoke_identity
from db.models import ExternalIdentity
from services.chat.rate_limit import allow_subject

logger = logging.getLogger(__name__)


async def _handle_telegram_message(
    text: str,
    chat_id: str,
    db: AsyncSession,
    telegram_user_id: int | str | None = None,
    chat_type: str = "private",
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
    
    if telegram_user_id is None:
        raise ValueError("telegram_sender_missing")
    is_private = chat_type == "private"
    identity = await resolve_identity(
        db,
        provider="telegram",
        external_id=telegram_user_id,
        channel="telegram" if is_private else "telegram_group",
    )
    if not is_private:
        identity = identity.__class__(None, None, "guest", "guest", identity.subject_hmac)
    user_role = identity.effective_role
    rate_limit = int(
        os.getenv(
            "TELEGRAM_RATE_LIMIT_GUEST_PER_MINUTE" if identity.account_role == "guest" else "TELEGRAM_RATE_LIMIT_AUTHENTICATED_PER_MINUTE",
            "10" if identity.account_role == "guest" else "30",
        )
    )
    if not await allow_subject(identity.subject_hmac, rate_limit):
        return "Alcanzaste el límite temporal de consultas. Probá nuevamente en un minuto."

    command, _, argument = user_text.partition(" ")
    command = command.lower().split("@", 1)[0]
    if command == "/vincular":
        if not is_private:
            return "Por seguridad, la vinculación sólo está disponible en un chat privado con el bot."
        if not argument.strip():
            return "Usá /vincular CODIGO con el código generado desde tu cuenta web."
        try:
            linked, account_role = await consume_link_code(db, code=argument.strip(), telegram_user_id=telegram_user_id)
        except (ValueError, PermissionError):
            return "El código no es válido, venció o la vinculación no está habilitada."
        if linked.status == "pending_approval":
            return "Identidad verificada. Falta la aprobación de un segundo administrador."
        return f"Vinculación activa. Tu rol de cuenta actual es {account_role}."
    if command == "/desvincular":
        if not identity.identity_id or not identity.user_id:
            return "No hay una identidad activa para desvincular."
        linked = await db.get(ExternalIdentity, identity.identity_id)
        if linked:
            await revoke_identity(db, linked, identity.user_id)
        return "La identidad de Telegram quedó revocada."
    if command == "/quien_soy":
        return f"Rol de cuenta: {identity.account_role}. Rol efectivo en este canal: {identity.effective_role}."
    if command == "/privacidad":
        return "Tu ID se cifra y se indexa con HMAC; no se muestra en logs. Podés revocar el vínculo con /desvincular."

    conversation_key = opaque_conversation_key("telegram", telegram_user_id, chat_id)
    telegram_session_id = f"telegram:{conversation_key[:48]}"
    opaque_user_identifier = f"tg:{identity.subject_hmac[:24]}"
    chat_session = await get_or_create_session(db, telegram_session_id, opaque_user_identifier)
    chat_session.channel = "telegram"
    chat_session.external_identity_id = identity.identity_id
    chat_session.subject_hmac = identity.subject_hmac
    chat_session.conversation_key = conversation_key
    await db.flush()
    
    # Recuperar historial reciente para contexto
    try:
        history_context = await get_recent_history(db, telegram_session_id, limit=6)
        logger.debug(f"Historial recuperado: {len(history_context) if history_context else 0} caracteres")
    except Exception as e:
        logger.debug("Error recuperando historial para Telegram: %s", type(e).__name__)
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
                    metadata={"intent": "diagnostico", "image_file_id": image_file_id},
                    user_identifier=opaque_user_identifier,
                )
                await save_message(
                    db, telegram_session_id, "assistant", diagnosis_result["diagnosis"],
                    metadata={"type": "diagnostico"}
                )
                await db.commit()
            except Exception as e:
                logger.error("Error guardando mensajes de Telegram: %s", type(e).__name__)
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
            logger.error("Error en diagnóstico de plantas desde Telegram: %s", type(e).__name__)
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
                    min_similarity=0.5,
                    role=user_role,
                    channel="telegram",
                )
                if rag_context:
                    logger.info("RAG: contexto autorizado encontrado para Telegram")
            except Exception as e:
                logger.debug("RAG search falló error=%s", type(e).__name__)
            
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
            if hasattr(provider, 'build_tools_schema'):
                tools_schema = await provider.build_tools_schema(user_role, "telegram")
            
            logger.debug(f"Preparando llamada a AIRouter con task={Task.SHORT_ANSWER.value}, intent=product_lookup")
            
            # Generar respuesta con tool calling
            try:
                logger.debug(f"Llamando a ai_router.run_async para consulta de producto...")
                answer = await ai_router.run_async(
                    task=Task.SHORT_ANSWER.value,
                    prompt=prompt_with_context,
                    user_context={"role": user_role, "channel": "telegram", "intent": "product_lookup"},
                    tools_schema=tools_schema,
                )
                logger.debug(f"Respuesta de ai_router.run_async recibida.")
            except Exception as e:
                logger.error("Error durante la llamada IA para producto: %s", type(e).__name__)
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
                    logger.error("Error intentando optimizar imagen a WebP: %s", type(e).__name__)

                logger.debug(f"Intentando enviar imagen: {clean_path}")
                try:
                    from services.notifications.telegram import send_photo
                    # Enviar la imagen
                    await send_photo(photo=clean_path, chat_id=chat_id)
                    logger.info(f"✓ Imagen enviada a Telegram: {clean_path} (raw: {raw_path})")
                except Exception as e:
                    logger.error("✗ Error enviando imagen Telegram: %s", type(e).__name__)
            
            answer = answer.strip()

            # Guardar mensaje del usuario y respuesta
            try:
                await save_message(
                    db, telegram_session_id, "user", user_text,
                    metadata={"intent": "product_lookup"},
                    user_identifier=opaque_user_identifier,
                )
                await save_message(
                    db, telegram_session_id, "assistant", answer,
                    metadata={"type": "product_answer"}
                )
                await db.commit()
            except Exception as e:
                logger.error("Error guardando mensajes de Telegram: %s", type(e).__name__)
                await db.rollback()
            
            return answer
            
        except Exception as e:
            logger.error("Error procesando consulta de producto en Telegram: %s", type(e).__name__)
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
                min_similarity=0.5,
                role=user_role,
                channel="telegram",
            )
            if rag_context:
                logger.info("RAG: contexto autorizado encontrado para chat general Telegram")
        except Exception as e:
            logger.debug("RAG search falló error=%s", type(e).__name__)
        
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
                "channel": "telegram",
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
                metadata={"intent": "chat_general"},
                user_identifier=opaque_user_identifier,
            )
            await save_message(
                db, telegram_session_id, "assistant", reply,
                metadata={"type": "chat_general"}
            )
            await db.commit()
        except Exception as e:
            logger.error("Error guardando mensajes de Telegram: %s", type(e).__name__)
            await db.rollback()
        
        return reply
        
    except Exception as e:
        logger.error("Error procesando mensaje general en Telegram: %s", type(e).__name__)
        return "Disculpá, hubo un error procesando tu mensaje. Probá más tarde."


async def handle_telegram_message(
    text: str,
    chat_id: str,
    db: AsyncSession,
    telegram_user_id: int | str | None = None,
    chat_type: str = "private",
    image_file_id: str | None = None,
) -> str:
    """Adapta Telegram al contexto y trazabilidad común del orquestador."""
    if telegram_user_id is None:
        raise ValueError("telegram_sender_missing")
    from services.chat.external_identity import resolve_identity
    from services.chat.orchestrator import ChatRequestContext, chat_orchestrator

    resolved = await resolve_identity(
        db,
        provider="telegram",
        external_id=telegram_user_id,
        channel="telegram",
    )
    account_role = resolved.account_role if chat_type == "private" else "guest"
    conversation_key = opaque_conversation_key("telegram", telegram_user_id, chat_id)
    context = ChatRequestContext.build(
        channel="telegram",
        conversation_id=f"telegram:{conversation_key[:48]}",
        account_role=account_role,
        external_identity_id=resolved.identity_id,
        user_id=resolved.user_id,
    )
    return await chat_orchestrator.execute(
        db,
        context,
        lambda: _handle_telegram_message(
            text=text,
            chat_id=chat_id,
            db=db,
            telegram_user_id=telegram_user_id,
            chat_type=chat_type,
            image_file_id=image_file_id,
        ),
    )

