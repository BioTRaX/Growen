"""Endpoint de chat síncrono que enruta intents y usa IA de respaldo."""

from fastapi import APIRouter
from pydantic import BaseModel

from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task
from services.intents.router import handle

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Modelo del cuerpo recibido en ``POST /chat``."""

    text: str


class ChatResponse(BaseModel):
    """Estructura común de salida del chat."""

    role: str = "assistant"
    text: str


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Procesa el mensaje y retorna la respuesta del intent o de la IA."""

    ai = AIRouter(settings)
    try:
        result = handle(req.text)
        reply = result.get("message", "")
    except KeyError:
        reply = ai.run(Task.SHORT_ANSWER.value, req.text)
    return ChatResponse(text=reply)
