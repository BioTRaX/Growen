"""WebSocket de chat que utiliza la IA de respaldo."""

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from services.ai.provider import ai_reply

router = APIRouter()


@router.websocket("/ws")
async def ws_chat(socket: WebSocket) -> None:
    """Canal WebSocket principal."""

    origin = socket.headers.get("origin")
    allowed = {"http://localhost:5173", "http://127.0.0.1:5173"}
    if origin not in allowed:
        await socket.close(code=1008)
        return
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
