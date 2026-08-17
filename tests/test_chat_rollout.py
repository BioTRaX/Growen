#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_rollout.py
# NG-HEADER: Ubicación: tests/test_chat_rollout.py
# NG-HEADER: Descripción: Pruebas del acceso gradual y rollback crítico de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import base64
from datetime import datetime

import pytest

from db.models import ChatRolloutCheck, ChatRolloutState
from services.chat.rollout import evaluate_auto_advance, telegram_access_allowed


@pytest.mark.asyncio
async def test_disabled_rollout_denies_telegram(db_session):
    db_session.add(ChatRolloutState(id=1, phase="disabled", status="paused", auto_advance=False))
    await db_session.commit()
    assert await telegram_access_allowed(db_session, account_role="guest", telegram_user_id=123) == (False, "rollout_paused")


@pytest.mark.asyncio
async def test_preflight_only_accepts_canary(db_session, monkeypatch):
    monkeypatch.delenv("TELEGRAM_IDENTITY_HMAC_KEY_FILE", raising=False)
    monkeypatch.delenv("TELEGRAM_CANARY_USER_ID_FILE", raising=False)
    monkeypatch.setenv("TELEGRAM_IDENTITY_HMAC_KEY", base64.urlsafe_b64encode(b"h" * 32).decode())
    monkeypatch.setenv("TELEGRAM_CANARY_USER_ID", "123")
    db_session.add(ChatRolloutState(id=1, phase="preflight", status="active", auto_advance=False, phase_started_at=datetime.utcnow()))
    await db_session.commit()
    assert (await telegram_access_allowed(db_session, account_role="guest", telegram_user_id=123))[0] is True
    assert (await telegram_access_allowed(db_session, account_role="guest", telegram_user_id=456))[0] is False


@pytest.mark.asyncio
async def test_critical_check_disables_and_pauses_rollout(db_session):
    db_session.add(ChatRolloutState(id=1, phase="guest", status="active", auto_advance=True, phase_started_at=datetime.utcnow()))
    db_session.add(ChatRolloutCheck(check_name="scope", phase="guest", status="failed", code="rag_scope_leak"))
    await db_session.commit()
    result = await evaluate_auto_advance(db_session)
    assert result["decision"] == "rollback"
    state = await db_session.get(ChatRolloutState, 1)
    assert state.phase == "disabled" and state.status == "paused"


@pytest.mark.asyncio
async def test_two_reliability_failures_roll_back_and_pause(db_session):
    db_session.add(ChatRolloutState(id=1, phase="collaborator", status="active", auto_advance=True, phase_started_at=datetime.utcnow()))
    db_session.add_all(
        [
            ChatRolloutCheck(check_name="reliability", phase="collaborator", status="failed", code="error_rate_high"),
            ChatRolloutCheck(check_name="reliability", phase="collaborator", status="failed", code="backlog_high"),
        ]
    )
    await db_session.commit()

    result = await evaluate_auto_advance(db_session)

    assert result == {
        "decision": "rollback",
        "phase": "linked_basic",
        "code": "reliability_failed_twice",
    }
    state = await db_session.get(ChatRolloutState, 1)
    assert state.phase == "linked_basic" and state.status == "paused"
