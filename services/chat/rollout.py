#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: rollout.py
# NG-HEADER: Ubicación: services/chat/rollout.py
# NG-HEADER: Descripción: Estado, acceso y decisiones automáticas del rollout de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.secrets import SecretConfigurationError, read_secret
from db.models import ChatRolloutCheck, ChatRolloutEvent, ChatRolloutState, ChatRun
from services.chat.external_identity import subject_hmac

PHASES = ("disabled", "preflight", "guest", "linked_basic", "collaborator", "admin_capped", "vue_eligible", "vue_active", "stable")
MIN_HOURS = {"preflight": 1, "guest": 24, "linked_basic": 24, "collaborator": 48, "admin_capped": 48, "vue_active": 24 * 7}
ROLE_PHASE = {"guest": "guest", "cliente": "linked_basic", "proveedor": "linked_basic", "colaborador": "collaborator", "admin": "admin_capped"}
CRITICAL_CODES = {"rag_scope_leak", "pii_leak", "telegram_mutation", "role_violation", "authorization_bypass"}
HEALTH_FILE = Path(__file__).resolve().parents[2] / "logs" / "telegram_health.json"


async def get_rollout_state(db: AsyncSession, *, lock: bool = False) -> ChatRolloutState:
    stmt = select(ChatRolloutState).where(ChatRolloutState.id == 1)
    if lock:
        stmt = stmt.with_for_update()
    state = await db.scalar(stmt)
    if state is None:
        state = ChatRolloutState(id=1, phase="disabled", status="paused", auto_advance=False, reason_code="initial_safe_state")
        db.add(state)
        await db.flush()
    return state


def _phase_at_least(current: str, required: str) -> bool:
    return current in PHASES and PHASES.index(current) >= PHASES.index(required)


async def telegram_access_allowed(db: AsyncSession, *, account_role: str, telegram_user_id: int | str) -> tuple[bool, str]:
    state = await get_rollout_state(db)
    if state.status != "active" or state.phase == "disabled":
        return False, "rollout_paused"
    if state.phase == "preflight":
        try:
            canary = read_secret("TELEGRAM_CANARY_USER_ID", required=True)
            assert canary is not None
            allowed = hmac.compare_digest(subject_hmac("telegram", telegram_user_id), subject_hmac("telegram", canary))
        except (SecretConfigurationError, RuntimeError):
            allowed = False
        return (allowed, "canary_only" if not allowed else "allowed")
    required = ROLE_PHASE.get(account_role, "admin_capped")
    return (_phase_at_least(state.phase, required), "phase_not_enabled" if not _phase_at_least(state.phase, required) else "allowed")


def _worker_health() -> dict[str, Any]:
    try:
        value = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


async def transition(
    db: AsyncSession,
    state: ChatRolloutState,
    to_phase: str,
    *,
    decision: str,
    result: str,
    reason_code: str,
    metrics: dict[str, Any] | None = None,
    pause: bool = False,
) -> ChatRolloutState:
    if to_phase not in PHASES:
        raise ValueError("rollout_phase_invalid")
    previous = state.phase
    state.phase = to_phase
    state.status = "paused" if pause else "active"
    state.paused_at = datetime.utcnow() if pause else None
    state.phase_started_at = datetime.utcnow()
    state.updated_at = datetime.utcnow()
    state.version += 1
    state.reason_code = reason_code
    db.add(ChatRolloutEvent(from_phase=previous, to_phase=to_phase, decision=decision, result=result, metrics=metrics or {}, reason_code=reason_code))
    await db.commit()
    return state


async def evaluate_auto_advance(db: AsyncSession) -> dict[str, Any]:
    state = await get_rollout_state(db, lock=True)
    failed_checks = (
        await db.scalars(select(ChatRolloutCheck).where(ChatRolloutCheck.created_at >= state.phase_started_at, ChatRolloutCheck.status == "failed"))
    ).all()
    critical = next((item for item in failed_checks if item.code in CRITICAL_CODES), None)
    if critical:
        await transition(db, state, "disabled", decision="automatic", result="rollback", reason_code=critical.code or "critical_gate", pause=True)
        return {"decision": "rollback", "phase": "disabled", "code": critical.code}
    reliability_checks = (
        await db.scalars(
            select(ChatRolloutCheck)
            .where(
                ChatRolloutCheck.phase == state.phase,
                ChatRolloutCheck.check_name == "reliability",
                ChatRolloutCheck.created_at >= state.phase_started_at,
            )
            .order_by(ChatRolloutCheck.created_at.desc())
            .limit(2)
        )
    ).all()
    if len(reliability_checks) == 2 and all(item.status == "failed" for item in reliability_checks):
        previous_index = max(0, PHASES.index(state.phase) - 1)
        previous_phase = PHASES[previous_index]
        await transition(
            db,
            state,
            previous_phase,
            decision="automatic",
            result="rollback",
            reason_code="reliability_failed_twice",
            pause=True,
        )
        return {"decision": "rollback", "phase": previous_phase, "code": "reliability_failed_twice"}
    if state.status != "active" or not state.auto_advance or state.phase in {"disabled", "stable"}:
        await db.commit()
        return {"decision": "hold", "phase": state.phase, "code": "automation_inactive"}

    runs = (
        await db.scalars(select(ChatRun).where(ChatRun.channel == "telegram", ChatRun.created_at >= state.phase_started_at))
    ).all()
    succeeded = sum(run.status == "succeeded" for run in runs)
    errors = sum(run.status == "failed" for run in runs)
    error_rate = errors / max(1, len(runs))
    latencies = sorted(run.latency_ms for run in runs if run.latency_ms is not None)
    p95 = latencies[min(len(latencies) - 1, int((len(latencies) - 1) * 0.95))] if latencies else None
    checks = (
        await db.scalars(select(ChatRolloutCheck).where(ChatRolloutCheck.phase == state.phase, ChatRolloutCheck.created_at >= state.phase_started_at))
    ).all()
    passed_names = {item.check_name for item in checks if item.status == "passed"}
    required_checks = {"ollama_generation", "ollama_embedding", "redis", "rag_eval", f"smoke_{state.phase}"}
    health = _worker_health()
    last_poll = None
    try:
        last_poll = datetime.fromisoformat(str(health.get("last_poll_at")))
    except (TypeError, ValueError):
        pass
    poll_fresh = bool(last_poll and last_poll >= datetime.utcnow() - timedelta(seconds=90))
    backlog = int(health.get("backlog") or 0)
    queue_size = max(1, int(__import__("os").getenv("TELEGRAM_POLLING_QUEUE_SIZE", "100")))
    min_hours = MIN_HOURS.get(state.phase, 0)
    elapsed_ok = datetime.utcnow() >= state.phase_started_at + timedelta(hours=min_hours)
    metrics = {"successful": succeeded, "error_rate": round(error_rate, 6), "p95_ms": p95, "backlog": backlog, "queue_size": queue_size, "poll_fresh": poll_fresh, "checks_passed": len(passed_names), "checks_required": len(required_checks)}
    reliable = succeeded >= 100 and error_rate <= 0.01 and p95 is not None and p95 <= 30_000 and backlog < queue_size * 0.8 and poll_fresh
    if not (elapsed_ok and reliable and required_checks <= passed_names):
        await db.commit()
        return {"decision": "hold", "phase": state.phase, "code": "gates_incomplete", "metrics": metrics}
    next_phase = PHASES[PHASES.index(state.phase) + 1]
    await transition(db, state, next_phase, decision="automatic", result="advanced", reason_code="all_gates_passed", metrics=metrics)
    return {"decision": "advanced", "phase": next_phase, "metrics": metrics}
