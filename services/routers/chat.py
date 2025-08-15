"""Endpoint de chat síncrono que enruta intents y usa IA de respaldo."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task
from services.intents.router import handle

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Modelo del cuerpo recibido en `/chat`.

    Se acepta tanto la clave `message` como `text` para compatibilidad con el
    frontend actual.
    """

    message: str = Field(alias="text")
    model_config = ConfigDict(populate_by_name=True)


@router.post("")
@router.post("/")
async def chat(req: ChatRequest) -> dict[str, object]:
    """Procesa el mensaje y retorna la respuesta del handler o de la IA."""

    ai = AIRouter(settings)
    try:
        return handle(req.message)
    except KeyError:
        reply = ai.run(Task.SHORT_ANSWER.value, req.message)
        return {"message": reply}
