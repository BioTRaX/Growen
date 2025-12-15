#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: cultivator.py
# NG-HEADER: Ubicación: services/chat/cultivator.py
# NG-HEADER: Descripción: Lógica de diagnóstico de plantas con visión y RAG
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de diagnóstico de plantas para el Modo Cultivador."""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.router import AIRouter
from ai.types import Task
from services.notifications.telegram import download_telegram_file
from services.rag.search import get_rag_search_service

logger = logging.getLogger(__name__)


async def get_image_base64_from_file_id(
    file_id: str,
    token: Optional[str] = None,
) -> Optional[str]:
    """
    Descarga imagen desde Telegram y la convierte a Base64.
    
    Args:
        file_id: File ID de Telegram
        token: Token del bot (opcional, usa TELEGRAM_BOT_TOKEN por defecto)
        
    Returns:
        Base64 string con formato "data:image/jpeg;base64,{base64_data}"
        o None si falla
    """
    if not file_id:
        return None
    
    try:
        # Descargar imagen desde Telegram
        image_bytes = await download_telegram_file(file_id, token=token)
        if not image_bytes:
            logger.warning(f"No se pudo descargar imagen con file_id: {file_id}")
            return None
        
        # Detectar MIME type desde los primeros bytes
        mime_type = "image/jpeg"  # Default
        if image_bytes.startswith(b'\x89PNG'):
            mime_type = "image/png"
        elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
            mime_type = "image/webp"
        elif image_bytes.startswith(b'\xff\xd8\xff'):
            mime_type = "image/jpeg"
        
        # Convertir a Base64
        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
        
    except Exception as e:
        logger.error(f"Error convirtiendo file_id a Base64: {e}")
        return None


async def diagnose_plant(
    user_input: str,
    image_file_id: Optional[str] = None,
    image_url: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    session: Optional[AsyncSession] = None,
    user_role: str = "guest",
) -> Dict[str, Any]:
    """
    Diagnostica problemas de plantas usando visión (si hay imagen), RAG y recomendaciones de productos.
    
    Flujo:
    1. Si hay imagen: analizar con visión para extraer síntomas visuales
    2. Buscar en RAG usando síntomas (visuales o textuales)
    3. Si confianza baja: generar pregunta de seguimiento
    4. Si diagnóstico firme: buscar productos por tags relacionados
    5. Clasificar productos en tres gamas (Baja, Media, Alta) por precio
    
    Args:
        user_input: Texto del usuario describiendo el problema
        image_file_id: File ID de Telegram (opcional)
        image_url: URL pública de imagen (opcional, alternativa a file_id)
        conversation_history: Historial de conversación (para contexto)
        session: Sesión de base de datos
        user_role: Rol del usuario
        
    Returns:
        Dict con:
        - diagnosis: Diagnóstico del problema
        - confidence: Nivel de confianza (0-1)
        - follow_up_question: Pregunta de seguimiento si confianza < 0.8
        - products: Lista de productos recomendados agrupados por gama
        - rag_context: Contexto relevante de la Knowledge Base
    """
    ai_router = AIRouter()
    rag_service = get_rag_search_service()
    
    # Paso 1: Análisis de imagen (si hay)
    visual_symptoms = ""
    images: List[str] = []
    
    if image_file_id:
        # Convertir File ID a Base64
        base64_image = await get_image_base64_from_file_id(image_file_id)
        if base64_image:
            images.append(base64_image)
            # Análisis de visión
            vision_prompt = (
                "Analiza esta imagen de una planta de cannabis. "
                "Describe los síntomas visibles: coloración de hojas (amarillo, marrón, verde), "
                "forma (deformaciones, enrollamiento, puntas secas), presencia de insectos, "
                "manchas, estado general. Sé específico y metódico. "
                "Responde solo con la descripción de síntomas, sin diagnósticos aún."
            )
            try:
                visual_symptoms = await ai_router.run_async(
                    task=Task.DIAGNOSIS_VISION.value,
                    prompt=vision_prompt,
                    user_context={"role": user_role, "intent": "diagnosis"},
                    images=images,
                )
                # Limpiar prefijo técnico si existe
                if ":" in visual_symptoms and visual_symptoms.split(":")[0].lower() in ("openai", "ollama"):
                    visual_symptoms = visual_symptoms.split(":", 1)[1].strip()
                logger.info(f"Síntomas visuales extraídos: {visual_symptoms[:100]}...")
            except Exception as e:
                logger.error(f"Error en análisis de visión: {e}")
                visual_symptoms = ""
    elif image_url:
        # Usar URL directamente (OpenAI acepta URLs públicas)
        images.append(image_url)
        # Análisis de visión con URL
        vision_prompt = (
            "Analiza esta imagen de una planta de cannabis. "
            "Describe los síntomas visibles: coloración de hojas (amarillo, marrón, verde), "
            "forma (deformaciones, enrollamiento, puntas secas), presencia de insectos, "
            "manchas, estado general. Sé específico y metódico. "
            "Responde solo con la descripción de síntomas, sin diagnósticos aún."
        )
        try:
            visual_symptoms = await ai_router.run_async(
                task=Task.DIAGNOSIS_VISION.value,
                prompt=vision_prompt,
                user_context={"role": user_role, "intent": "diagnosis"},
                images=images,
            )
            # Limpiar prefijo técnico si existe
            if ":" in visual_symptoms and visual_symptoms.split(":")[0].lower() in ("openai", "ollama"):
                visual_symptoms = visual_symptoms.split(":", 1)[1].strip()
            logger.info(f"Síntomas visuales extraídos: {visual_symptoms[:100]}...")
        except Exception as e:
            logger.error(f"Error en análisis de visión: {e}")
            visual_symptoms = ""
    
    # Paso 2: Búsqueda RAG usando síntomas (visuales o textuales)
    rag_context = ""
    search_query = visual_symptoms if visual_symptoms else user_input
    
    if session and search_query:
        try:
            rag_context = await rag_service.search_and_format_context(
                search_query,
                session,
                top_k=5,
                min_similarity=0.6,
            )
            if rag_context:
                logger.info("Contexto RAG encontrado para diagnóstico")
        except Exception as e:
            logger.error(f"Error en búsqueda RAG: {e}")
            rag_context = ""
    
    # Paso 3: Generar diagnóstico completo
    diagnosis_prompt_parts = []
    
    if visual_symptoms:
        diagnosis_prompt_parts.append(f"Síntomas visuales observados:\n{visual_symptoms}\n\n")
    
    if user_input:
        diagnosis_prompt_parts.append(f"Descripción del usuario:\n{user_input}\n\n")
    
    if rag_context:
        diagnosis_prompt_parts.append(f"Contexto relevante de documentación:\n{rag_context}\n\n")
    
    diagnosis_prompt_parts.append(
        "Basándote en los síntomas y el contexto, diagnostica el problema de la planta. "
        "Explica qué puede estar causando el problema y qué nivel de confianza tienes (alto, medio, bajo). "
        "Si la confianza es baja, sugiere una pregunta de seguimiento clave (ej: '¿Mides pH?', '¿Las hojas amarillas empiezan por abajo o por arriba?'). "
        "Responde en formato claro y educativo."
    )
    
    diagnosis_prompt = "".join(diagnosis_prompt_parts)
    
    try:
        diagnosis_response = await ai_router.run_async(
            task=Task.DIAGNOSIS_VISION.value if images else Task.REASONING.value,
            prompt=diagnosis_prompt,
            user_context={"role": user_role, "intent": "diagnosis"},
            images=images if images else None,
        )
        # Limpiar prefijo técnico si existe
        if ":" in diagnosis_response and diagnosis_response.split(":")[0].lower() in ("openai", "ollama"):
            diagnosis_response = diagnosis_response.split(":", 1)[1].strip()
    except Exception as e:
        logger.error(f"Error generando diagnóstico: {e}")
        diagnosis_response = "No pude generar un diagnóstico en este momento. Por favor, intenta de nuevo."
    
    # Paso 4: Extraer confianza y pregunta de seguimiento (heurística simple)
    confidence = 0.7  # Default medio
    follow_up_question = None
    
    diagnosis_lower = diagnosis_response.lower()
    if "confianza alta" in diagnosis_lower or "confianza alta" in diagnosis_lower or "estoy seguro" in diagnosis_lower:
        confidence = 0.9
    elif "confianza baja" in diagnosis_lower or "confianza baja" in diagnosis_lower or "no estoy seguro" in diagnosis_lower:
        confidence = 0.5
        # Intentar extraer pregunta de seguimiento
        if "?" in diagnosis_response:
            sentences = diagnosis_response.split(".")
            for sent in sentences:
                if "?" in sent:
                    follow_up_question = sent.strip()
                    break
    
    # Paso 5: Buscar productos por tags relacionados (si diagnóstico es firme)
    products_by_tier = {"low": [], "medium": [], "high": []}
    
    if confidence >= 0.7 and session:
        # Extraer tags relevantes del diagnóstico
        # Heurística: buscar términos comunes de problemas y mapear a tags
        tag_mapping = {
            "plaga": ["#Plagas", "#Acaricida", "#Insecticida"],
            "ácaros": ["#Acaricida", "#Plagas"],
            "pulgones": ["#Insecticida", "#Plagas"],
            "carencia": ["#Nutrientes", "#Fertilizante"],
            "nitrógeno": ["#Nitrogeno", "#Fertilizante"],
            "fósforo": ["#Fosforo", "#Fertilizante"],
            "potasio": ["#Potasio", "#Fertilizante"],
            "hongos": ["#Fungicida", "#Hongos"],
            "moho": ["#Fungicida", "#Hongos"],
            "orgánico": ["#Organico"],
            "mineral": ["#Mineral"],
        }
        
        # Buscar tags relevantes en el diagnóstico
        relevant_tags = []
        diagnosis_lower = diagnosis_response.lower()
        for keyword, tags in tag_mapping.items():
            if keyword in diagnosis_lower:
                relevant_tags.extend(tags)
        
        # Si hay tags relevantes, buscar productos
        if relevant_tags:
            try:
                import httpx
                import os
                
                # Obtener URL base de la API
                api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
                
                # Normalizar tags (remover # y convertir a nombres)
                tag_names = [t.lstrip("#") for t in relevant_tags]
                tags_param = ",".join(tag_names[:3])  # Máximo 3 tags para la búsqueda
                
                # Llamar al endpoint de búsqueda por tags
                url = f"{api_base_url}/catalog/search_by_tags"
                params = {"tags": tags_param, "limit": 20}
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        products_found = data.get("items", [])
                        
                        # Clasificar productos por precio en tres gamas
                        for prod in products_found:
                            price = prod.get("price")
                            if price is None:
                                continue
                            
                            # Heurística de gamas (ajustar según precios del catálogo)
                            if price < 5000:  # Gama baja
                                products_by_tier["low"].append(prod)
                            elif price < 15000:  # Gama media
                                products_by_tier["medium"].append(prod)
                            else:  # Gama alta
                                products_by_tier["high"].append(prod)
                        
                        # Limitar a 3 productos por gama
                        products_by_tier["low"] = products_by_tier["low"][:3]
                        products_by_tier["medium"] = products_by_tier["medium"][:3]
                        products_by_tier["high"] = products_by_tier["high"][:3]
                        
                        logger.info(f"Productos encontrados por tags: {len(products_found)} total, "
                                  f"{len(products_by_tier['low'])} baja, "
                                  f"{len(products_by_tier['medium'])} media, "
                                  f"{len(products_by_tier['high'])} alta")
                    else:
                        logger.warning(f"Error en búsqueda por tags: {resp.status_code}")
            except Exception as e:
                logger.error(f"Error buscando productos por tags: {e}")
                # Continuar sin productos recomendados
    
    return {
        "diagnosis": diagnosis_response,
        "confidence": confidence,
        "follow_up_question": follow_up_question,
        "products": products_by_tier,
        "rag_context": rag_context[:500] if rag_context else "",  # Limitar tamaño
        "visual_symptoms": visual_symptoms[:200] if visual_symptoms else "",
    }

