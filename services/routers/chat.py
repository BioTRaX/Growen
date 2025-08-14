"""Endpoint básico de chat por HTTP."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def post_chat(data: ChatRequest) -> ChatResponse:
    """Devuelve una respuesta dummy.

    Esta ruta sirve como fallback cuando el WebSocket no está disponible.
    """
    return ChatResponse(reply=f"Echo: {data.message}")
