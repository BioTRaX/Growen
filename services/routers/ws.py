"""WebSocket de chat con ruteo de intents e IA de respaldo."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task
from services.intents.router import handle

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def ws_chat(socket: WebSocket) -> None:
    """Canal WebSocket principal.

    Se valida el encabezado `Origin` para aceptar solo conexiones provenientes
    del frontend en `localhost:5173`.
    """

    origin = socket.headers.get("origin")
    allowed = {"http://localhost:5173", "http://127.0.0.1:5173"}
    if origin not in allowed:
        await socket.close(code=1008)  # violación de política
        return
    await socket.accept()
    ai = AIRouter(settings)
    try:
        while True:
            data = await socket.receive_text()
            try:
                result = handle(data)
                reply = result.get("message", "")
            except KeyError:
                reply = ai.run(Task.SHORT_ANSWER.value, data)
            await socket.send_json({"role": "assistant", "text": reply})
    except WebSocketDisconnect:
        # El cliente cerró la conexión; no es necesario llamar a ``close``.
        pass
    except Exception as exc:
        logger.exception("Error inesperado en ws_chat")
        try:
            await socket.send_json({"role": "system", "text": f"error: {exc}"})
        except Exception:
            pass
