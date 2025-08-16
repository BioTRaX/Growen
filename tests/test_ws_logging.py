import logging

from test_ws_chat import client


def test_ws_logs_disconnect(caplog):
    """Registra advertencia cuando el cliente se desconecta."""
    with caplog.at_level(logging.WARNING):
        with client.websocket_connect("/ws") as ws:
            ws.close()
    assert any(
        "Cliente desconectado" in record.message for record in caplog.records
    )


def test_ws_logs_ai_error(monkeypatch, caplog):
    """Registra error y notifica al cliente."""
    async def boom(prompt: str) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr("services.routers.ws.ai_reply", boom)

    with caplog.at_level(logging.ERROR):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hola")
            data = ws.receive_json()
    assert data == {"role": "system", "text": "error: boom"}
    assert any(
        "Error inesperado en ws_chat" in record.message for record in caplog.records
    )
