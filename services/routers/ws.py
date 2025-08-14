"""WebSocket de chat con ruteo de intents e IA de respaldo."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task
from services.intents.router import handle

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/chat")
async def ws_chat(socket: WebSocket) -> None:
    await socket.accept()
    ai = AIRouter(settings)
    try:
        while True:
            data = await socket.receive_text()
            try:
                result = handle(data)
            except KeyError:
                reply = ai.run(Task.SHORT_ANSWER.value, data)
                result = {"message": reply}
            await socket.send_json(result)
    except WebSocketDisconnect:
        await socket.close(code=1000)
    except Exception:
        logger.exception("Error inesperado en ws_chat")
        await socket.close(code=1011)
        raise
