# NG-HEADER: Nombre de archivo: chat.py
# NG-HEADER: Ubicación: services/routers/chat.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoint de chat síncrono que consulta la IA."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.ai.provider import ai_reply

router = APIRouter()


class ChatIn(BaseModel):
    """Modelo del cuerpo recibido en ``POST /chat``."""

    text: str


class ChatOut(BaseModel):
    """Estructura común de salida del chat."""

    role: str = "assistant"
    text: str


@router.post("/chat", response_model=ChatOut)
async def chat_endpoint(payload: ChatIn) -> ChatOut:
    """Llama a la IA y normaliza la respuesta."""

    reply = await ai_reply(payload.text)
    return ChatOut(text=reply)
