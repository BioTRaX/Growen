"""Endpoint de chat síncrono."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("/")
async def chat(req: ChatRequest) -> dict[str, str]:
    """Echo simple del mensaje recibido."""
    return {"reply": f"Recibido: {req.message}"}
