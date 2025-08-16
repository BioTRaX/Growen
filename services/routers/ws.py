"""WebSocket de chat que utiliza la IA de respaldo."""

from datetime import datetime

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from db.models import Session as DBSess
from db.session import SessionLocal
from starlette.websockets import WebSocketDisconnect

from services.ai.provider import ai_reply

router = APIRouter()


@router.websocket("/ws")
async def ws_chat(socket: WebSocket) -> None:
    """Canal WebSocket principal."""

    sid = socket.cookies.get("growen_session")
    if sid:
        async with SessionLocal() as db:
            res = await db.execute(
                select(DBSess).where(
                    DBSess.id == sid, DBSess.expires_at > datetime.utcnow()
                )
            )
            sess = res.scalar_one_or_none()
            if not sess:
                sid = None

    await socket.accept()
    try:
        while True:
            data = await socket.receive_text()
            reply = await ai_reply(data)
            await socket.send_json({"role": "assistant", "text": reply})
    except WebSocketDisconnect:
        # El cliente cerró la conexión; no es necesario llamar a ``close``.
        pass
    except Exception as exc:
        try:
            await socket.send_json({"role": "system", "text": f"error: {exc}"})
        except Exception:
            pass
