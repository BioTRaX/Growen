"""Comunicación de chat vía WebSocket con streaming."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_ws(socket: WebSocket) -> None:
    """Recibe mensajes y envía una respuesta simulada por chunks."""
    await socket.accept()
    try:
        while True:
            await socket.receive_json()
            # Respuesta simple enviada en tres partes
            for chunk in ["Hola ", "Growen", "!"]:
                await socket.send_json(
                    {"role": "assistant", "content": chunk, "done": False}
                )
                await asyncio.sleep(0.1)
            await socket.send_json({"role": "assistant", "content": "", "done": True})
    except WebSocketDisconnect:
        pass
