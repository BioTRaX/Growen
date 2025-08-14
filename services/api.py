"""Aplicación FastAPI principal del agente."""
from fastapi import FastAPI

from agent_core.config import settings
from ai.router import AIRouter
from .routers import actions, chat, ws

app = FastAPI(title="Growen")
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Devuelve OK si la aplicación está viva."""
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai() -> dict[str, list[str]]:
    """Informa los proveedores disponibles de IA."""
    router = AIRouter(settings)
    return {"providers": router.available_providers()}
