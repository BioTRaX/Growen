# NG-HEADER: Nombre de archivo: test_ws_chat.py
# NG-HEADER: Ubicación: tests/test_ws_chat.py
# NG-HEADER: Descripción: Pruebas asíncronas del canal WebSocket de chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from websockets.asyncio.client import connect

from db.models import ChatRun, Session as DBSess, User
from agent_core.chat_policy import current_chat_citations
from db.session import SessionLocal
from services.auth import hash_session_id
from services.chat.memory import build_memory_key, clear_memory, ensure_memory
from services.chat.price_lookup import ProductQuery


@pytest.mark.asyncio
async def test_ws_without_session(monkeypatch, live_asgi_server) -> None:
    """Debe responder y registrar la ejecución aunque no haya sesión."""
    called = {}

    async def fake_ai(prompt: str) -> str:
        called["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("services.routers.ws.ai_reply", fake_ai)
    async with connect(f"{live_asgi_server['ws']}/ws") as ws:
        await ws.send("hola")
        data = json.loads(await ws.recv())

    assert called["prompt"] == "hola"
    assert data["role"] == "assistant"
    assert data["text"] == "ok"
    assert data["correlation_id"].startswith("ws-")
    async with SessionLocal() as db:
        count = await db.scalar(select(func.count(ChatRun.id)).where(ChatRun.channel == "websocket"))
    assert int(count or 0) >= 1


@pytest.mark.asyncio
async def test_ws_with_session(monkeypatch, live_asgi_server) -> None:
    """Personaliza el prompt con el nombre y el rol actual del usuario."""
    called = {}

    async def fake_ai(prompt: str) -> str:
        called["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("services.routers.ws.ai_reply", fake_ai)
    async with SessionLocal() as db:
        user = User(identifier="u1", password_hash="x", role="cliente", name="User Uno")
        db.add(user)
        await db.flush()
        db.add(DBSess(id=hash_session_id("sid1"), user_id=user.id, role=user.role, csrf_token="tok", expires_at=datetime.utcnow() + timedelta(minutes=5)))
        await db.commit()

    async with connect(f"{live_asgi_server['ws']}/ws", additional_headers={"Cookie": "growen_session=sid1"}) as ws:
        await ws.send("hola")
        data = json.loads(await ws.recv())

    assert "User Uno" in called["prompt"] and "cliente" in called["prompt"]
    assert data["role"] == "assistant"
    assert data["text"] == "ok"
    assert data["correlation_id"].startswith("ws-")


@pytest.mark.asyncio
async def test_ws_returns_rag_citations_from_orchestrator(monkeypatch, live_asgi_server) -> None:
    citation = {
        "source_id": 7,
        "title": "Guía controlada",
        "chunk_index": 1,
        "page": None,
        "score": 0.91,
        "content_version": 2,
    }

    async def fake_rag(prompt: str, _query: str, _db, *, role: str) -> str:
        assert role == "guest"
        current_chat_citations.set((citation,))
        return f"{prompt}\ncontexto"

    async def fake_ai(prompt: str) -> str:
        assert prompt.endswith("contexto")
        return "respuesta con fuente"

    monkeypatch.setattr("services.routers.ws._add_rag_context", fake_rag)
    monkeypatch.setattr("services.routers.ws.ai_reply", fake_ai)
    async with connect(f"{live_asgi_server['ws']}/ws") as ws:
        await ws.send("consulta de cultivo")
        data = json.loads(await ws.recv())

    assert data["text"] == "respuesta con fuente"
    assert data["citations"] == [citation]


@pytest.mark.asyncio
async def test_ws_clarification_is_orchestrated_and_correlated(live_asgi_server, monkeypatch) -> None:
    user_agent = "growen-ws-test"
    memory_key = build_memory_key(session_id=None, role="guest", host="127.0.0.1", user_agent=user_agent)
    query = ProductQuery(raw_text="precio sustrato", normalized_text="precio sustrato", terms=["sustrato"], sku_candidates=[], has_price=True, has_stock=False, intent="price")
    ensure_memory(memory_key, query, pending=True, rendered="")
    monkeypatch.setattr("services.routers.ws.extract_product_query", lambda _text: None)
    try:
        async with connect(f"{live_asgi_server['ws']}/ws", user_agent_header=user_agent) as ws:
            await ws.send("...")
            data = json.loads(await ws.recv())
        assert data["type"] == "clarify_prompt"
        assert data["intent"] == "clarify"
        assert data["correlation_id"].startswith("ws-")
        async with SessionLocal() as db:
            run = await db.scalar(select(ChatRun).where(ChatRun.correlation_id == data["correlation_id"]))
        assert run is not None and run.status == "succeeded"
    finally:
        clear_memory(memory_key)
