#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: chat_rollout.py
# NG-HEADER: Ubicación: services/routers/chat_rollout.py
# NG-HEADER: Descripción: Administración segura del rollout de Chat sin avance forzado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from services.auth import SessionData, require_csrf, require_roles
from services.chat.rollout import PHASES, get_rollout_state, transition

router = APIRouter(prefix="/admin/chat-rollout", tags=["Admin - Chat rollout"])


def _serialize(state) -> dict:
    return {"phase": state.phase, "status": state.status, "auto_advance": state.auto_advance, "phase_started_at": state.phase_started_at.isoformat(), "paused_at": state.paused_at.isoformat() if state.paused_at else None, "version": state.version, "reason_code": state.reason_code}


@router.get("")
async def rollout_status(_session: SessionData = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    return _serialize(await get_rollout_state(db))


@router.post("/pause", dependencies=[Depends(require_csrf)])
async def pause_rollout(_session: SessionData = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    state = await get_rollout_state(db, lock=True)
    state.status = "paused"
    state.paused_at = datetime.utcnow()
    state.reason_code = "manual_pause"
    await db.commit()
    return _serialize(state)


@router.post("/resume", dependencies=[Depends(require_csrf)])
async def resume_rollout(_session: SessionData = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    state = await get_rollout_state(db, lock=True)
    if state.phase == "disabled":
        raise HTTPException(status_code=409, detail="rollout_disabled_requires_preflight_configuration")
    state.status = "active"
    state.paused_at = None
    state.reason_code = "manual_resume"
    await db.commit()
    return _serialize(state)


@router.post("/rollback", dependencies=[Depends(require_csrf)])
async def rollback_rollout(_session: SessionData = Depends(require_roles("admin")), db: AsyncSession = Depends(get_session)):
    state = await get_rollout_state(db, lock=True)
    current_index = PHASES.index(state.phase)
    target = PHASES[max(0, current_index - 1)]
    return _serialize(await transition(db, state, target, decision="manual", result="rollback", reason_code="manual_rollback", pause=True))
