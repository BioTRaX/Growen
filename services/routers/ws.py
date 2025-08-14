"""Comunicación de chat vía WebSocket con streaming."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ai import ChatMsg, complete

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_ws(socket: WebSocket) -> None:
    """Recibe mensajes y envía respuestas generadas por IA."""
    await socket.accept()
    try:
        while True:
            data = await socket.receive_json()
            text = data.get("message", "")
            if any(k in text.lower() for k in ["seo", "descripción", "redact", "mejorar"]):
                task = "seo.product_desc" if "seo" in text.lower() else "content.generation"
            else:
                task = "short_answer"
            messages = [ChatMsg(role="user", content=text)]
            async for chunk in complete(task, messages, stream=True):
                await socket.send_json(chunk)
    except WebSocketDisconnect:
        pass
