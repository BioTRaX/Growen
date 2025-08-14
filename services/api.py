"""Aplicación principal de FastAPI."""

from fastapi import FastAPI

from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_provider import OpenAIProvider
from .routers import chat, actions, ws

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    """Verifica que el servicio esté vivo."""
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai() -> dict[str, dict[str, str]]:
    """Consulta el estado de salud de los proveedores de IA."""
    providers = {
        "ollama": OllamaProvider(),
        "openai": OpenAIProvider(),
    }
    result: dict[str, dict[str, str]] = {}
    for name, provider in providers.items():
        result[name] = await provider.healthcheck()
    return result


# Registro de routers secundarios
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(ws.router)
