"""Aplicación FastAPI principal del agente."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from agent_core.config import settings
from ai.router import AIRouter
from .routers import actions, chat, ws, catalog, imports, canonical_products

# `redirect_slashes=False` evita redirecciones 307 entre `/ruta` y `/ruta/`,
# lo que rompe las solicitudes *preflight* de CORS.
app = FastAPI(title="Growen", redirect_slashes=False)

# Permitir que el frontend consulte la API sin errores de CORS.
# Se lee la lista desde la variable de entorno ``ALLOWED_ORIGINS`` separada
# por comas. Si se especifica ``localhost`` o ``127.0.0.1`` se agrega su
# contraparte automáticamente para evitar fallos entre ambos hostnames.
raw_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
origins_set = set(raw_origins)
for url in list(raw_origins):
    if "localhost" in url:
        origins_set.add(url.replace("localhost", "127.0.0.1"))
    if "127.0.0.1" in url:
        origins_set.add(url.replace("127.0.0.1", "localhost"))
origins = sorted(origins_set)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    # Solo se habilitan los métodos necesarios y se permiten credenciales.
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(actions.router)
app.include_router(ws.router)
app.include_router(catalog.router)
app.include_router(imports.router)
app.include_router(canonical_products.canonical_router)
app.include_router(canonical_products.equivalences_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Devuelve OK si la aplicación está viva."""
    return {"status": "ok"}


@app.get("/health/ai")
async def health_ai() -> dict[str, list[str]]:
    """Informa los proveedores disponibles de IA."""
    router = AIRouter(settings)
    return {"providers": router.available_providers()}
