#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: orchestrator.py
# NG-HEADER: Ubicación: services/chat/orchestrator.py
# NG-HEADER: Descripción: Contexto multicanal y trazabilidad segura de ejecuciones.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Contrato común para ejecutar y medir respuestas de chat."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Awaitable, Callable, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.chat_policy import current_chat_citations, current_chat_rag_cache_hit, current_chat_run_id, effective_role, normalize_role
from db.models import ChatRun, ChatSession, ChatToolEvent

T = TypeVar("T")


@dataclass(frozen=True)
class ChatRequestContext:
    channel: str
    conversation_id: str
    account_role: str = "guest"
    effective_role: str = "guest"
    external_identity_id: int | None = None
    user_id: int | None = None
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def build(
        cls,
        *,
        channel: str,
        conversation_id: str,
        account_role: str,
        external_identity_id: int | None = None,
        user_id: int | None = None,
        correlation_id: str | None = None,
    ) -> "ChatRequestContext":
        role = normalize_role(account_role)
        return cls(
            channel=channel,
            conversation_id=conversation_id,
            account_role=role,
            effective_role=effective_role(role, channel),
            external_identity_id=external_identity_id,
            user_id=user_id,
            correlation_id=correlation_id or uuid.uuid4().hex,
        )


class ChatOrchestrator:
    """Envuelve el pipeline de canal con métricas sin prompts ni resultados."""

    async def execute(
        self,
        db: AsyncSession,
        context: ChatRequestContext,
        operation: Callable[[], Awaitable[T]],
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> T:
        run = ChatRun(
            id=uuid.uuid4().hex,
            session_id=None,
            correlation_id=context.correlation_id,
            channel=context.channel,
            account_role=context.account_role,
            effective_role=context.effective_role,
            provider=provider,
            model=model,
            status="running",
        )
        db.add(run)
        await db.commit()
        context_token = current_chat_run_id.set(run.id)
        citation_token = current_chat_citations.set(())
        cache_token = current_chat_rag_cache_hit.set(False)
        started = time.perf_counter()
        try:
            result = await operation()
            if hasattr(result, "citations"):
                setattr(result, "citations", list(current_chat_citations.get()))
            run.status = "succeeded"
            if await db.get(ChatSession, context.conversation_id):
                run.session_id = context.conversation_id
            return result
        except Exception as exc:
            run.status = "failed"
            run.error_code = type(exc).__name__[:64]
            raise
        finally:
            run.latency_ms = int((time.perf_counter() - started) * 1000)
            run.completed_at = datetime.utcnow()
            citations = current_chat_citations.get()
            run.rag_used = bool(citations)
            run.citation_count = len(citations)
            run.cache_hit = current_chat_rag_cache_hit.get()
            run.tool_count = int(await db.scalar(select(func.count(ChatToolEvent.id)).where(ChatToolEvent.run_id == run.id)) or 0)
            try:
                await db.commit()
            finally:
                current_chat_rag_cache_hit.reset(cache_token)
                current_chat_citations.reset(citation_token)
                current_chat_run_id.reset(context_token)


async def archive_expired_sessions(db: AsyncSession, days: int) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        update(ChatSession)
        .where(ChatSession.status != "archived", ChatSession.last_message_at < cutoff)
        .values(status="archived", updated_at=datetime.utcnow())
    )
    await db.commit()
    return int(result.rowcount or 0)


chat_orchestrator = ChatOrchestrator()
