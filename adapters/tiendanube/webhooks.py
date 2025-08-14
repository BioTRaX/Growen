"""Webhook de ejemplo para Tiendanube."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhooks/tiendanube", tags=["tiendanube"])


@router.post("/")
async def receive(request: Request) -> dict[str, str]:
    payload = await request.json()
    return {"status": "received", "event": payload.get("event", "unknown")}
