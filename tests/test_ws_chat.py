import os
import asyncio
from datetime import datetime, timedelta

# Configurar DB en memoria antes de importar la app
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient

from services.api import app
from db.base import Base
from db.session import engine, SessionLocal
from db.models import User, Session as DBSess


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)


def test_ws_without_session(monkeypatch) -> None:
    """Debe responder aunque no haya sesión."""
    client.cookies.clear()
    called = {}

    async def fake_ai(prompt: str) -> str:
        called["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("services.routers.ws.ai_reply", fake_ai)

    with client.websocket_connect("/ws") as ws:
        ws.send_text("hola")
        data = ws.receive_json()

    assert called["prompt"] == "hola"
    assert data == {"role": "assistant", "text": "ok"}


def test_ws_with_session(monkeypatch) -> None:
    """Personaliza el prompt con el nombre y rol del usuario."""
    client.cookies.clear()
    called = {}

    async def fake_ai(prompt: str) -> str:
        called["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("services.routers.ws.ai_reply", fake_ai)

    async def _create_session() -> None:
        async with SessionLocal() as db:
            user = User(identifier="u1", password_hash="x", role="cliente", name="User Uno")
            db.add(user)
            await db.flush()
            sess = DBSess(
                id="sid1",
                user_id=user.id,
                role=user.role,
                csrf_token="tok",
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            )
            db.add(sess)
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_create_session())
    client.cookies.set("growen_session", "sid1")

    with client.websocket_connect("/ws") as ws:
        ws.send_text("hola")
        data = ws.receive_json()

    assert "User Uno" in called["prompt"] and "cliente" in called["prompt"]
    assert data == {"role": "assistant", "text": "ok"}
