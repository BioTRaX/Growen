"""Aplicación FastAPI principal del agente."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_core.config import settings
from ai.router import AIRouter
from .routers import actions, chat, ws, catalog

# `redirect_slashes=False` evita redirecciones 307 entre `/ruta` y `/ruta/`,
# lo que rompe las solicitudes *preflight* de CORS.
app = FastAPI(title="Growen", redirect_slashes=False)

# Permitir que el frontend de desarrollo (Vite) consulte la API sin errores de
# CORS. Se limita a `localhost:5173` y `127.0.0.1:5173`.
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(ws.router)
app.include_router(catalog.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Devuelve OK si la aplicación está viva."""
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai() -> dict[str, list[str]]:
    """Informa los proveedores disponibles de IA."""
    router = AIRouter(settings)
    return {"providers": router.available_providers()}
