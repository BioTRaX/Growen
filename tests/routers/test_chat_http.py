import pytest
from httpx import AsyncClient

from services.api import app

pytestmark = pytest.mark.asyncio

async def test_chat_http_basic():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/chat", json={"text": "Hola, ¿quién sos?"})
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "assistant"
        # Debe contener parte de la pregunta (eco del stub) pero no incluir el system prompt completo varias veces
        assert "Hola" in data["text"]
        # El system prompt empieza con "Sos Growen."; si está, debería ser solo una vez máximo
        assert data["text"].count("Sos Growen.") <= 1
