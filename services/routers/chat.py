# NG-HEADER: Nombre de archivo: chat.py
# NG-HEADER: Ubicación: services/routers/chat.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoint de chat síncrono que consulta la IA."""

from fastapi import APIRouter
from pydantic import BaseModel

from agent_core.config import settings as core_settings
from ai.router import AIRouter
from ai.types import Task

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
    """Llama a la IA usando AIRouter (inyecta SYSTEM_PROMPT)."""

    router = AIRouter(core_settings)
    raw = router.run(Task.SHORT_ANSWER.value, payload.text)
    # Recortar system prompt si el stub devuelve todo el prompt completo.
    if "\n\n" in raw:
        reply = raw.split("\n\n")[-1].strip()
    else:
        reply = raw.strip()
    return ChatOut(text=reply)
