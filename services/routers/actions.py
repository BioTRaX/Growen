"""Lista de acciones rápidas disponibles."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Action(BaseModel):
    label: str
    command: str


@router.get("/actions", response_model=list[Action])
async def list_actions() -> list[Action]:
    """Devuelve comandos predefinidos para la interfaz."""
    return [
        Action(label="Pull catálogo (dry-run)", command="/sync pull --dry-run"),
        Action(label="Push cambios (dry-run)", command="/sync push --dry-run"),
        Action(label="Push cambios (APLICAR)", command="/sync push --apply"),
        Action(
            label="Ajustar stock por SKU", command="/stock adjust --sku=SKU --qty=1"
        ),
    ]
