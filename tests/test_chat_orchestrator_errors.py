#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_orchestrator_errors.py
# NG-HEADER: Ubicación: tests/test_chat_orchestrator_errors.py
# NG-HEADER: Descripción: Valida trazabilidad segura de fallos del orquestador Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from sqlalchemy import select

from db.models import ChatRun
from services.chat.orchestrator import ChatRequestContext, ChatOrchestrator


class ControlledError(RuntimeError):
    code = "controlled_processing_failed"


@pytest.mark.asyncio
async def test_orchestrator_persists_safe_failure_code(db_session):
    context = ChatRequestContext.build(
        channel="telegram",
        conversation_id="telegram:test-error",
        account_role="guest",
    )

    async def fail():
        raise ControlledError("detalle no persistible")

    with pytest.raises(ControlledError):
        await ChatOrchestrator().execute(db_session, context, fail, input_text="contenido privado")

    run = await db_session.scalar(select(ChatRun).where(ChatRun.correlation_id == context.correlation_id))
    assert run is not None
    assert run.status == "failed"
    assert run.error_code == "controlled_processing_failed"
    assert "contenido privado" not in str(run.error_code)
