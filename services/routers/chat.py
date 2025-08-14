"""Endpoint básico de chat por HTTP."""

from fastapi import APIRouter
from pydantic import BaseModel

from ai import ChatMsg, complete

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def post_chat(data: ChatRequest) -> ChatResponse:
    """Redirige el mensaje del usuario al router de IA.

    Se elige una tarea simple según el contenido: mensajes cortos usan
    ``short_answer`` mientras que textos con palabras clave relacionadas a
    redacción o SEO emplean modelos de OpenAI.
    """

    text = data.message.lower()
    if any(k in text for k in ["seo", "descripción", "redact", "mejorar"]):
        task = "seo.product_desc" if "seo" in text else "content.generation"
    else:
        task = "short_answer"

    messages = [ChatMsg(role="user", content=data.message)]
    chunks: list[str] = []
    async for chunk in complete(task, messages, stream=False):
        chunks.append(chunk["content"])
    return ChatResponse(reply="".join(chunks))
