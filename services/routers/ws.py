"""WebSocket de chat básico."""
from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/chat")
async def ws_chat(socket: WebSocket) -> None:
    await socket.accept()
    try:
        while True:
            data = await socket.receive_text()
            await socket.send_text(f"echo: {data}")
    except Exception:
        await socket.close()
