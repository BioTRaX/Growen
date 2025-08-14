"""Aplicación principal de FastAPI."""

from fastapi import FastAPI

from .routers import chat, actions, ws

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    """Verifica que el servicio esté vivo."""
    return {"status": "ok"}


# Registro de routers secundarios
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(ws.router)
