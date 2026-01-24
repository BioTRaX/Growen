#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: cultivator.py
# NG-HEADER: Ubicación: services/chat/cultivator.py
# NG-HEADER: Descripción: Lógica de diagnóstico de plantas con visión, RAG y recomendaciones NPK
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio de diagnóstico de plantas para el Modo Cultivador."""
from __future__ import annotations

import base64
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.router import AIRouter
from ai.types import Task
from services.notifications.telegram import download_telegram_file
from services.rag.search import get_rag_search_service

logger = logging.getLogger(__name__)


# --- Utilidades NPK ---

def parse_npk_from_tags(tags: List[str]) -> Optional[Dict[str, float]]:
    """
    Parsea tags buscando formato NPK X-X-X.
    
    Soporta formatos:
    - "NPK 10-2,4-6" (español con comas)
    - "NPK 10-2.4-6" (inglés con puntos)
    - "NPK 10-2,4-6 + Zinc(Zn) 0.09%..." (con extras)
    
    Args:
        tags: Lista de tags del producto (ej: ["NPK 10-2,4-6 + Zinc...", "#Organico"])
        
    Returns:
        {"N": 10.0, "P": 2.4, "K": 6.0} o None si no encuentra
    """
    for tag in tags:
        if not tag:
            continue
        # Buscar patrón NPK X-X-X (con decimales opcionales, comas o puntos)
        match = re.search(
            r'NPK\s*(\d+(?:[.,]\d+)?)-(\d+(?:[.,]\d+)?)-(\d+(?:[.,]\d+)?)',
            tag,
            re.IGNORECASE
        )
        if match:
            # Normalizar comas a puntos para parseo
            n_val = float(match.group(1).replace(',', '.'))
            p_val = float(match.group(2).replace(',', '.'))
            k_val = float(match.group(3).replace(',', '.'))
            return {"N": n_val, "P": p_val, "K": k_val}
    return None


def filter_products_by_deficiency(
    products: List[Dict[str, Any]], 
    deficiency: str,
    only_with_stock: bool = True
) -> List[Dict[str, Any]]:
    """
    Filtra productos por carencia detectada usando lógica NPK.
    
    Mapeo de carencias:
    - Carencia Nitrógeno → Alto N (primer dígito >= 10)
    - Carencia Fósforo → Alto P (segundo dígito >= 10)
    - Carencia Potasio → Alto K (tercer dígito >= 10)
    - Carencia Calcio/Magnesio → Buscar "CalMag", "Ca", "Mg" en tags
    
    Args:
        products: Lista de productos con campo "tags" y "stock"
        deficiency: String describiendo la carencia (ej: "carencia de nitrógeno")
        only_with_stock: Si True, solo retorna productos con stock > 0
        
    Returns:
        Lista filtrada de productos ordenada por relevancia
    """
    deficiency_lower = deficiency.lower()
    filtered = []
    
    for product in products:
        # Filtro de stock si aplica
        if only_with_stock and (product.get("stock", 0) or 0) <= 0:
            continue
            
        tags = product.get("tags", [])
        npk = parse_npk_from_tags(tags)
        tags_lower = " ".join(t.lower() for t in tags if t)
        
        # Score de relevancia (mayor = mejor)
        score = 0
        
        # Mapeo carencia → nutriente requerido
        if "nitrógeno" in deficiency_lower or "nitrogeno" in deficiency_lower:
            if npk and npk["N"] >= 10:
                score = npk["N"]
            elif "nitrogeno" in tags_lower or "nitrógeno" in tags_lower or "veg" in tags_lower:
                score = 5
                
        elif "fósforo" in deficiency_lower or "fosforo" in deficiency_lower:
            if npk and npk["P"] >= 10:
                score = npk["P"]
            elif "fosforo" in tags_lower or "fósforo" in tags_lower or "bloom" in tags_lower:
                score = 5
                
        elif "potasio" in deficiency_lower:
            if npk and npk["K"] >= 10:
                score = npk["K"]
            elif "potasio" in tags_lower or "pk" in tags_lower or "bloom" in tags_lower:
                score = 5
                
        elif "calcio" in deficiency_lower or "magnesio" in deficiency_lower:
            if "calmag" in tags_lower or "calcio" in tags_lower or "magnesio" in tags_lower:
                score = 10
            elif "ca" in tags_lower or "mg" in tags_lower:
                score = 5
                
        elif "hierro" in deficiency_lower or "fe" in deficiency_lower:
            if "hierro" in tags_lower or "fe" in tags_lower or "iron" in tags_lower:
                score = 10
        
        if score > 0:
            product["_relevance_score"] = score
            filtered.append(product)
    
    # Ordenar por score de relevancia (descendente)
    filtered.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)
    
    # Limpiar campo temporal
    for p in filtered:
        p.pop("_relevance_score", None)
    
    return filtered


def classify_products_by_price_tier(
    products: List[Dict[str, Any]], 
    max_per_tier: int = 1
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Clasifica productos en tres gamas de precio.
    
    Args:
        products: Lista de productos con campo "price"
        max_per_tier: Máximo de productos por gama
        
    Returns:
        {"low": [...], "medium": [...], "high": [...]}
    """
    # Ordenar por precio
    priced = [p for p in products if p.get("price") is not None]
    priced.sort(key=lambda p: p.get("price", 0))
    
    if not priced:
        return {"low": [], "medium": [], "high": []}
    
    # Dividir en terciles
    n = len(priced)
    if n == 1:
        return {"low": [], "medium": priced[:1], "high": []}
    elif n == 2:
        return {"low": priced[:1], "medium": [], "high": priced[1:2]}
    else:
        tercile = n // 3
        return {
            "low": priced[:max_per_tier],
            "medium": priced[tercile:tercile + max_per_tier],
            "high": priced[-max_per_tier:],
        }




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
    from agent_core.config import settings as core_settings
    ai_router = AIRouter(core_settings)
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
    
    # Construir prompt con enfoque conversacional (Farmacéutico)
    # El LLM debe hacer preguntas antes de diagnosticar
    conversational_prompt_parts = []
    
    if conversation_history:
        # Si hay historial, el LLM tiene contexto previo
        conversational_prompt_parts.append(f"Historial reciente:\n{conversation_history}\n")
    
    if visual_symptoms:
        conversational_prompt_parts.append(f"Síntomas visuales observados:\n{visual_symptoms}\n")
    
    if user_input:
        conversational_prompt_parts.append(f"Mensaje del usuario:\n{user_input}\n")
    
    if rag_context:
        conversational_prompt_parts.append(f"Contexto técnico relevante:\n{rag_context}\n")
    
    # Instrucción de diagnóstico conversacional
    conversational_prompt_parts.append("""
Responde como experto cultivador conversando naturalmente.

ANÁLISIS DE CONTEXTO OBLIGATORIO:
1. Revisa el historial y el mensaje actual buscando el MEDIO de cultivo (Hidroponia/DWC vs Tierra/Sustrato).
2. Revisa la ETAPA de la planta (Vegetativo vs Floración).
3. Adapta tus preguntas y consejos a este contexto (ej: pH 5.8 hidro vs 6.5 tierra).

Si es la PRIMERA mención del problema (sin historial de preguntas previas):
1. Reconoce el síntoma mencionado
2. Si NO sabes el medio de cultivo, PREGUNTA: "¿Estás en tierra o hidro?"
3. Haz UNA pregunta clave de diagnóstico diferencial adaptada al medio.
4. NO recomiendes productos todavía

Si ya hubo intercambio de preguntas Y tenés suficiente información:
1. Da tu diagnóstico con nivel de confianza
2. Explica brevemente la causa probable (contextualizando al medio)
3. Pregunta: "¿Querés que te busque productos para esto?"

Responde en español rioplatense casual. Sé breve y natural.""")
    
    full_diagnosis_prompt = "\n".join(conversational_prompt_parts)
    
    try:
        diagnosis_response = await ai_router.run_async(
            task=Task.DIAGNOSIS_VISION.value if images else Task.REASONING.value,
            prompt=full_diagnosis_prompt,
            user_context={
                "role": user_role, 
                "intent": "DIAGNOSTICO",  # Intent correcto para activar persona CULTIVATOR
                "conversation_state": {"current_mode": "CULTIVATOR"},
            },
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
    if "confianza alta" in diagnosis_lower or "estoy seguro" in diagnosis_lower:
        confidence = 0.9
    elif "confianza baja" in diagnosis_lower or "no estoy seguro" in diagnosis_lower:
        confidence = 0.5
        # Intentar extraer pregunta de seguimiento
        if "?" in diagnosis_response:
            sentences = diagnosis_response.split(".")
            for sent in sentences:
                if "?" in sent:
                    follow_up_question = sent.strip()
                    break
    
    # Paso 5: Detectar carencia del diagnóstico y buscar productos con NPK relevante
    products_by_tier = {"low": [], "medium": [], "high": []}
    detected_deficiency = None
    
    # Mapeo de términos de diagnóstico a carencias
    deficiency_keywords = {
        "nitrógeno": "carencia de nitrógeno",
        "nitrogeno": "carencia de nitrógeno", 
        "fósforo": "carencia de fósforo",
        "fosforo": "carencia de fósforo",
        "potasio": "carencia de potasio",
        "calcio": "carencia de calcio",
        "magnesio": "carencia de magnesio",
        "calmag": "carencia de calcio",
        "hierro": "carencia de hierro",
    }
    
    # Detectar carencia mencionada en el diagnóstico
    for keyword, deficiency in deficiency_keywords.items():
        if keyword in diagnosis_lower and ("carencia" in diagnosis_lower or "deficiencia" in diagnosis_lower or "falta" in diagnosis_lower):
            detected_deficiency = deficiency
            break
    
    if confidence >= 0.7 and session and detected_deficiency:
        # Buscar productos por tags relevantes y filtrar por NPK
        tag_mapping = {
            "nitrógeno": ["Fertilizante", "Vegetativo", "Nitrogeno"],
            "fósforo": ["Fertilizante", "Floracion", "Fosforo"],
            "potasio": ["Fertilizante", "Floracion", "Potasio", "PK"],
            "calcio": ["CalMag", "Calcio", "Micronutrientes"],
            "magnesio": ["CalMag", "Magnesio", "Micronutrientes"],
            "hierro": ["Hierro", "Micronutrientes", "Quelatos"],
        }
        
        # Determinar tags a buscar según la carencia
        relevant_tags = []
        for keyword, tags in tag_mapping.items():
            if keyword in detected_deficiency.lower():
                relevant_tags.extend(tags)
                break
        
        if not relevant_tags:
            relevant_tags = ["Fertilizante"]  # Fallback genérico
        
        try:
            import httpx
            import os
            
            api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
            tags_param = ",".join(relevant_tags[:3])
            
            # Llamar al endpoint de búsqueda por tags
            url = f"{api_base_url}/catalog/search_by_tags"
            params = {"tags": tags_param, "limit": 30}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    products_found = data.get("items", [])
                    
                    # Filtrar por NPK según la carencia detectada (solo con stock > 0)
                    filtered_products = filter_products_by_deficiency(
                        products_found, 
                        detected_deficiency,
                        only_with_stock=True  # Recomendación proactiva: solo con stock
                    )
                    
                    # Clasificar por precio en tres gamas
                    products_by_tier = classify_products_by_price_tier(filtered_products, max_per_tier=1)
                    
                    total_recommended = sum(len(v) for v in products_by_tier.values())
                    logger.info(
                        f"Productos NPK recomendados para '{detected_deficiency}': "
                        f"{total_recommended} total (low: {len(products_by_tier['low'])}, "
                        f"medium: {len(products_by_tier['medium'])}, high: {len(products_by_tier['high'])})"
                    )
                else:
                    logger.warning(f"Error en búsqueda por tags: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error buscando productos por NPK: {e}")
    
    return {
        "diagnosis": diagnosis_response,
        "confidence": confidence,
        "follow_up_question": follow_up_question,
        "products": products_by_tier,
        "detected_deficiency": detected_deficiency,  # Nuevo: para flujo de conversación
        "rag_context": rag_context[:500] if rag_context else "",
        "visual_symptoms": visual_symptoms[:200] if visual_symptoms else "",
    }


