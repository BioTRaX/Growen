#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_quality_pipeline.py
# NG-HEADER: Ubicación: tests/test_chat_quality_pipeline.py
# NG-HEADER: Descripción: Pruebas del feedback y gobierno reversible de prompts.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest

from ai.prompt_registry import resolve
from db.models import ChatMessage, ChatSession


@pytest.mark.asyncio
async def test_feedback_y_promocion_supervisada(client, db_session):
    chat = ChatSession(session_id="web:quality-1", user_identifier="quality-1", channel="web", status="new")
    db_session.add(chat)
    await db_session.flush()
    message = ChatMessage(session_id=chat.session_id, role="assistant", content="Respuesta a revisar")
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    feedback = await client.post(
        f"/admin/chat-quality/messages/{message.id}/feedback",
        json={"rating": "negative", "categories": ["precision"], "comment": "Dato incorrecto"},
    )
    assert feedback.status_code == 200

    candidate = await client.post(
        "/admin/chat-quality/prompts/candidates",
        json={"prompt_key": "persona.observer", "content": "Prompt candidato suficientemente extenso y seguro para las pruebas.", "reason": "Mejorar precisión", "manual": True},
    )
    assert candidate.status_code == 200
    prompt_id = candidate.json()["id"]

    evaluated = await client.post(
        f"/admin/chat-quality/prompts/{prompt_id}/evaluate",
        json={"dataset_version": "quality-v1", "sample_count": 50, "composite_score": 0.82, "safety_passed": True, "details": {}},
    )
    assert evaluated.status_code == 200
    assert (await client.post(f"/admin/chat-quality/prompts/{prompt_id}/approve")).status_code == 200
    assert (await client.post(f"/admin/chat-quality/prompts/{prompt_id}/activate")).status_code == 200
    assert resolve("persona.observer", "fallback") == "Prompt candidato suficientemente extenso y seguro para las pruebas."


@pytest.mark.asyncio
async def test_no_aprueba_prompt_sin_evaluacion_de_seguridad(client):
    candidate = await client.post(
        "/admin/chat-quality/prompts/candidates",
        json={"prompt_key": "persona.salesman", "content": "Prompt candidato sin evaluación que no debe llegar a producción.", "manual": True},
    )
    response = await client.post(f"/admin/chat-quality/prompts/{candidate.json()['id']}/approve")
    assert response.status_code == 409
