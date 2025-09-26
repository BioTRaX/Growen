# NG-HEADER: Nombre de archivo: webhooks.py
# NG-HEADER: Ubicación: adapters/tiendanube/webhooks.py
# NG-HEADER: Descripción: Procesa webhooks entrantes provenientes de Tiendanube.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Webhook de ejemplo para Tiendanube."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks/tiendanube", tags=["tiendanube"])


@router.post("/")
async def receive(request: Request) -> dict[str, str]:
    payload = await request.json()
    return {"status": "received", "event": payload.get("event", "unknown")}
