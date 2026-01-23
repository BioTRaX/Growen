"""
Módulo para clasificar la intención del usuario utilizando un LLM.
"""
from __future__ import annotations
from enum import Enum
import logging

from ai.router import AIRouter
from ai.types import Task

logger = logging.getLogger(__name__)

class UserIntent(Enum):
    """Define las intenciones que el sistema puede reconocer."""
    VENTA_CONVERSACIONAL = "VENTA_CONVERSACIONAL"
    CONSULTA_PRECIO = "CONSULTA_PRECIO"
    CHAT_GENERAL = "CHAT_GENERAL"
    DIAGNOSTICO = "DIAGNOSTICO"  # NUEVO: Consulta diagnóstica de plantas
    UNKNOWN = "UNKNOWN"


INTENT_CLASSIFICATION_PROMPT_TEMPLATE = """
You are an expert intent classifier for a business management application. Your task is to determine the user's primary intent based on their message.
Choose one of the following intents. Respond with ONLY the intent name and nothing else.

Available Intents:
- VENTA_CONVERSACIONAL: The user wants to create, start, or continue registering a sale. Keywords: "vende", "registra", "factura", "anota una venta", "quiero vender".
- CONSULTA_PRECIO: The user is asking for the price or stock of a product. Keywords: "cuánto cuesta", "precio", "valor", "stock", "hay de".
- DIAGNOSTICO: The user is asking for plant diagnosis, describing plant problems, asking about image analysis capabilities, or sending images of plants. Keywords: "hojas amarillas", "plaga", "carencia", "qué le pasa", "diagnóstico", "problema", "enfermedad", "hongos", "insectos", "se muere", "se seca", "analizar imagen", "ver foto", "puedes ver", "mira esto", "subir foto", "analizar fotos", "diagnosticar por imagen".
- CHAT_GENERAL: This is a general conversation, a greeting, a question not related to other intents, or a follow-up response to a question from the assistant.

User message: "{user_text}"

Based on the user message, the single most likely intent is:
"""

async def classify_intent(ai_router: AIRouter, user_text: str) -> UserIntent:
    """
    Clasifica el texto del usuario en una de las intenciones predefinidas usando un LLM.

    Args:
        ai_router: La instancia del router de IA para comunicarse con el LLM.
        user_text: El mensaje del usuario.

    Returns:
        El enum UserIntent correspondiente a la intención clasificada.
    """
    prompt = INTENT_CLASSIFICATION_PROMPT_TEMPLATE.format(user_text=user_text)
    
    try:
        # Usamos run_async para clasificación asíncrona
        raw_response = await ai_router.run_async(
            task=Task.SHORT_ANSWER.value,
            prompt=prompt,
            user_context={"intent": "classification"}
        )
        
        # Limpiar prefijo técnico si existe (openai:, ollama:)
        if ":" in raw_response and raw_response.split(":")[0].lower() in ("openai", "ollama"):
            raw_response = raw_response.split(":", 1)[1].strip()
        
        # Limpiamos la respuesta del LLM para obtener solo el nombre de la intención.
        # Los modelos a veces añaden espacios o texto extra.
        cleaned_response = raw_response.strip().upper()

        # Intentamos convertir la respuesta de texto a nuestro Enum.
        return UserIntent(cleaned_response)

    except (ValueError, KeyError) as e:
        # Si el LLM devuelve algo que no está en nuestro Enum, lo marcamos como UNKNOWN.
        logger.warning(f"Error al clasificar la intención. Respuesta: '{raw_response}'. Error: {e}")
        return UserIntent.UNKNOWN
    except Exception as e:
        # Captura cualquier otro error durante la llamada a la API de la IA.
        logger.error(f"Error inesperado en la clasificación de intención: {e}")
        return UserIntent.UNKNOWN
