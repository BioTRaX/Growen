#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: chat_quality.py
# NG-HEADER: Ubicación: services/routers/chat_quality.py
# NG-HEADER: Descripción: Feedback, clasificación y promoción reversible de prompts de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Pipeline administrativo de calidad y aprendizaje supervisado del Chat Inbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.prompt_registry import ActivePrompt, activate
from db.models import (
    AIPromptEvaluation,
    AIPromptVersion,
    ChatMessage,
    ChatMessageFeedback,
    ChatSession,
    User,
)
from db.session import SessionLocal, get_session
from services.auth import SessionData, require_csrf, require_roles

router = APIRouter(prefix="/admin/chat-quality", tags=["Admin - Chat Quality"])


class FeedbackIn(BaseModel):
    rating: str
    categories: list[str] = Field(default_factory=list, max_length=20)
    comment: str | None = Field(None, max_length=2000)


class BulkUpdateIn(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=100)
    status: str | None = None
    assigned_user_id: int | None = None
    tags: dict[str, Any] | None = None


class CandidateIn(BaseModel):
    prompt_key: str = Field(pattern=r"^persona\.[a-z_]+$", max_length=100)
    content: str | None = Field(None, min_length=20, max_length=50000)
    reason: str | None = Field(None, max_length=2000)
    manual: bool = False


class EvaluationIn(BaseModel):
    dataset_version: str = Field(min_length=1, max_length=64)
    sample_count: int = Field(ge=1)
    composite_score: float = Field(ge=0, le=1)
    safety_passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


def _user_id(session: SessionData) -> int | None:
    return session.user.id if session.user else None


def _prompt_out(prompt: AIPromptVersion) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "prompt_key": prompt.prompt_key,
        "version": prompt.version,
        "status": prompt.status,
        "content": prompt.content,
        "reason": prompt.reason,
        "metrics": prompt.metrics,
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "approved_at": prompt.approved_at.isoformat() if prompt.approved_at else None,
        "activated_at": prompt.activated_at.isoformat() if prompt.activated_at else None,
    }


@router.post("/messages/{message_id}/feedback", dependencies=[Depends(require_csrf)])
async def save_feedback(
    message_id: int,
    payload: FeedbackIn,
    session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    if payload.rating not in {"positive", "negative"}:
        raise HTTPException(400, detail="rating debe ser positive o negative")
    message = await db.get(ChatMessage, message_id)
    if not message or message.role != "assistant":
        raise HTTPException(404, detail="Respuesta del asistente no encontrada")
    reviewer_id = _user_id(session)
    feedback = await db.scalar(select(ChatMessageFeedback).where(
        ChatMessageFeedback.message_id == message_id,
        ChatMessageFeedback.reviewer_user_id == reviewer_id,
    ))
    if feedback is None:
        feedback = ChatMessageFeedback(message_id=message_id, reviewer_user_id=reviewer_id, rating=payload.rating)
        db.add(feedback)
    feedback.rating = payload.rating
    feedback.categories = payload.categories
    feedback.comment = payload.comment
    feedback.updated_at = datetime.utcnow()
    await db.commit()
    return {"id": feedback.id, "status": "saved"}


@router.get("/metrics")
async def quality_metrics(
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    rows = (await db.execute(select(ChatMessageFeedback.rating, func.count()).group_by(ChatMessageFeedback.rating))).all()
    ratings = {str(rating): count for rating, count in rows}
    intents = (await db.execute(select(ChatSession.detected_intent, func.count()).where(ChatSession.detected_intent.isnot(None)).group_by(ChatSession.detected_intent))).all()
    sentiments = (await db.execute(select(ChatSession.sentiment, func.count()).where(ChatSession.sentiment.isnot(None)).group_by(ChatSession.sentiment))).all()
    return {
        "feedback": ratings,
        "intents": {str(key): count for key, count in intents},
        "sentiments": {str(key): count for key, count in sentiments},
        "total_feedback": sum(ratings.values()),
    }


@router.get("/staff")
async def list_staff(
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    users = (await db.execute(select(User).where(User.role.in_(["admin", "colaborador"])).order_by(User.name, User.identifier))).scalars().all()
    return {"items": [{"id": user.id, "name": user.name or user.identifier or user.email or f"Usuario {user.id}", "role": user.role} for user in users]}


def _classify_text(text: str) -> tuple[str, str, float, list[str]]:
    lowered = text.lower()
    negative_terms = ("mal", "error", "no funciona", "enoj", "queja", "problema")
    positive_terms = ("gracias", "excelente", "perfecto", "bien", "sirvió")
    intents = {
        "diagnostico": ("hoja", "plaga", "planta", "hongo", "carencia"),
        "precio_stock": ("precio", "stock", "cuesta", "disponible"),
        "compra": ("comprar", "pedido", "envío", "pagar"),
    }
    intent = next((name for name, terms in intents.items() if any(term in lowered for term in terms)), "consulta_general")
    negative = sum(term in lowered for term in negative_terms)
    positive = sum(term in lowered for term in positive_terms)
    sentiment = "negative" if negative > positive else "positive" if positive > negative else "neutral"
    signals = [name for name, terms in {"frustration": negative_terms, "safety": ("veneno", "tóxico", "ingerir")}.items() if any(term in lowered for term in terms)]
    confidence = min(0.95, 0.58 + 0.07 * max(negative, positive, 1))
    return intent, sentiment, confidence, signals


async def _classify_session(session_id: str) -> None:
    async with SessionLocal() as db:
        session = await db.get(ChatSession, session_id)
        if not session:
            return
        messages = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id, ChatMessage.role == "user").order_by(ChatMessage.created_at))).scalars().all()
        intent, sentiment, confidence, signals = _classify_text("\n".join(message.content for message in messages))
        session.detected_intent = intent
        session.sentiment = sentiment
        session.classification_confidence = confidence
        session.classification_model = "rules-es-v1"
        session.problem_signals = signals
        session.classified_at = datetime.utcnow()
        await db.commit()


@router.post("/sessions/{session_id}/classify", status_code=202, dependencies=[Depends(require_csrf)])
async def classify_session(
    session_id: str,
    tasks: BackgroundTasks,
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    if await db.get(ChatSession, session_id) is None:
        raise HTTPException(404, detail="Sesión no encontrada")
    tasks.add_task(_classify_session, session_id)
    return {"status": "queued", "session_id": session_id}


@router.post("/sessions/bulk", dependencies=[Depends(require_csrf)])
async def bulk_update(
    payload: BulkUpdateIn,
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    if payload.status is not None and payload.status not in {"new", "reviewed", "archived"}:
        raise HTTPException(400, detail="Estado inválido")
    if payload.assigned_user_id is not None:
        assignee = await db.get(User, payload.assigned_user_id)
        if not assignee or assignee.role not in {"admin", "colaborador"}:
            raise HTTPException(400, detail="El responsable debe ser un usuario staff")
    sessions = (await db.execute(select(ChatSession).where(ChatSession.session_id.in_(payload.session_ids)))).scalars().all()
    for chat in sessions:
        if payload.status is not None:
            chat.status = payload.status
        if payload.assigned_user_id is not None:
            chat.assigned_user_id = payload.assigned_user_id
        if payload.tags is not None:
            chat.tags = {**(chat.tags or {}), **payload.tags}
    await db.commit()
    return {"updated": len(sessions)}


@router.get("/prompts")
async def list_prompts(
    prompt_key: str | None = None,
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    query = select(AIPromptVersion).order_by(AIPromptVersion.prompt_key, desc(AIPromptVersion.version))
    if prompt_key:
        query = query.where(AIPromptVersion.prompt_key == prompt_key)
    return {"items": [_prompt_out(row) for row in (await db.execute(query)).scalars().all()]}


@router.post("/prompts/candidates", dependencies=[Depends(require_csrf)])
async def create_candidate(
    payload: CandidateIn,
    session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    last = await db.scalar(select(AIPromptVersion).where(AIPromptVersion.prompt_key == payload.prompt_key).order_by(desc(AIPromptVersion.version)).limit(1))
    since = last.created_at if last else datetime.min
    feedback_rows = (await db.execute(select(ChatMessageFeedback).where(ChatMessageFeedback.created_at > since))).scalars().all()
    negatives = [row for row in feedback_rows if row.rating == "negative"]
    if not payload.manual and (len(feedback_rows) < 50 or len(negatives) < 10):
        raise HTTPException(409, detail={"message": "Umbral de feedback no alcanzado", "total": len(feedback_rows), "negative": len(negatives)})
    base = await db.scalar(select(AIPromptVersion).where(AIPromptVersion.prompt_key == payload.prompt_key, AIPromptVersion.status == "active"))
    content = payload.content
    if not content:
        if not base:
            raise HTTPException(400, detail="La primera versión requiere contenido")
        failure_categories = sorted({category for row in negatives for category in (row.categories or [])})
        content = base.content + "\n\nMejoras supervisadas: evitá especialmente " + ", ".join(failure_categories or ["las fallas indicadas por revisores"])
    prompt = AIPromptVersion(
        prompt_key=payload.prompt_key,
        version=(last.version + 1 if last else 1),
        status="candidate",
        content=content,
        reason=payload.reason,
        metrics={"feedback_count": len(feedback_rows), "negative_count": len(negatives)},
        created_by_user_id=_user_id(session),
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return _prompt_out(prompt)


@router.post("/prompts/{prompt_id}/evaluate", dependencies=[Depends(require_csrf)])
async def evaluate_prompt(
    prompt_id: int,
    payload: EvaluationIn,
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    prompt = await db.get(AIPromptVersion, prompt_id)
    if not prompt or prompt.status not in {"candidate", "approved"}:
        raise HTTPException(404, detail="Candidato no encontrado")
    evaluation = AIPromptEvaluation(prompt_version_id=prompt_id, **payload.model_dump())
    db.add(evaluation)
    prompt.metrics = {**(prompt.metrics or {}), "latest_score": payload.composite_score, "safety_passed": payload.safety_passed, "dataset_version": payload.dataset_version}
    await db.commit()
    return {"id": evaluation.id, "status": "evaluated"}


@router.post("/prompts/{prompt_id}/approve", dependencies=[Depends(require_csrf)])
async def approve_prompt(
    prompt_id: int,
    session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    prompt = await db.get(AIPromptVersion, prompt_id)
    if not prompt or prompt.status != "candidate":
        raise HTTPException(404, detail="Candidato no encontrado")
    evaluation = await db.scalar(select(AIPromptEvaluation).where(AIPromptEvaluation.prompt_version_id == prompt_id).order_by(desc(AIPromptEvaluation.created_at)).limit(1))
    if not evaluation or not evaluation.safety_passed:
        raise HTTPException(409, detail="Se requiere una evaluación sin regresión de seguridad")
    active = await db.scalar(select(AIPromptVersion).where(AIPromptVersion.prompt_key == prompt.prompt_key, AIPromptVersion.status == "active"))
    baseline = 0.0
    if active:
        active_eval = await db.scalar(select(AIPromptEvaluation).where(AIPromptEvaluation.prompt_version_id == active.id).order_by(desc(AIPromptEvaluation.created_at)).limit(1))
        baseline = float(active_eval.composite_score) if active_eval else float((active.metrics or {}).get("latest_score", 0))
    required = baseline * 1.05
    if float(evaluation.composite_score) < required:
        raise HTTPException(409, detail={"message": "Mejora mínima del 5 % no alcanzada", "required": required})
    prompt.status = "approved"
    prompt.approved_by_user_id = _user_id(session)
    prompt.approved_at = datetime.utcnow()
    await db.commit()
    return _prompt_out(prompt)


@router.post("/prompts/{prompt_id}/activate", dependencies=[Depends(require_csrf)])
async def activate_prompt(
    prompt_id: int,
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    prompt = await db.get(AIPromptVersion, prompt_id)
    if not prompt or prompt.status not in {"approved", "retired"}:
        raise HTTPException(409, detail="La versión debe estar aprobada")
    previous = (await db.execute(select(AIPromptVersion).where(AIPromptVersion.prompt_key == prompt.prompt_key, AIPromptVersion.status == "active"))).scalars().all()
    for row in previous:
        row.status = "retired"
    prompt.status = "active"
    prompt.activated_at = datetime.utcnow()
    await db.commit()
    activate(ActivePrompt(prompt.id, prompt.prompt_key, prompt.version, prompt.content))
    return {**_prompt_out(prompt), "previous_ids": [row.id for row in previous]}
