#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_history.py
# NG-HEADER: Ubicación: tests/test_chat_history.py
# NG-HEADER: Descripción: Pruebas del presupuesto por tokens del historial Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import pytest

from services.chat.history import get_recent_history, save_message


@pytest.mark.asyncio
async def test_recent_history_prefers_newest_messages_within_budget(db_session) -> None:
    session_id = "web:history-budget"
    await save_message(db_session, session_id, "user", "antiguo " + "a" * 80, user_identifier="web:opaque")
    await save_message(db_session, session_id, "assistant", "intermedio " + "b" * 80, user_identifier="web:opaque")
    await save_message(db_session, session_id, "user", "reciente " + "c" * 80, user_identifier="web:opaque")
    await db_session.commit()

    history = await get_recent_history(db_session, session_id, max_tokens=30)
    assert "reciente" in history
    assert "antiguo" not in history


@pytest.mark.asyncio
async def test_recent_history_keeps_chronological_order(db_session) -> None:
    session_id = "web:history-order"
    await save_message(db_session, session_id, "user", "primero", user_identifier="web:opaque")
    await save_message(db_session, session_id, "assistant", "segundo", user_identifier="web:opaque")
    await db_session.commit()

    history = await get_recent_history(db_session, session_id, max_tokens=100)
    assert history.index("primero") < history.index("segundo")
