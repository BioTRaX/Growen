# NG-HEADER: Nombre de archivo: actions.py
# NG-HEADER: Ubicación: services/routers/actions.py
# NG-HEADER: Descripción: Endpoints de acciones rápidas y diagnósticos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Lista de acciones rápidas disponibles."""
from fastapi import APIRouter

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("/")
async def actions() -> list[dict[str, str]]:
    """Retorna acciones predefinidas para la interfaz."""
    return [
        {"command": "/help", "description": "Muestra ayuda"},
        {"command": "/sync pull --dry-run", "description": "Simula la sincronización"},
    ]
