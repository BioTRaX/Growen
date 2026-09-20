#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: external_identities.py
# NG-HEADER: Ubicación: services/routers/external_identities.py
# NG-HEADER: Descripción: API segura de vinculación y administración de identidades externas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints web para vincular, aprobar y revocar Telegram."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ExternalIdentity, User
from db.session import get_session
from services.auth import SessionData, current_session, require_csrf, require_roles, verify_pw
from services.chat.external_identity import create_link_request, masked_identity, revoke_identity
from agent_core.config import settings

router = APIRouter(tags=["external-identities"])


class LinkRequestInput(BaseModel):
    password: str


def _require_user(session: SessionData) -> User:
    if not session.user:
        raise HTTPException(status_code=401, detail="authentication_required")
    return session.user


@router.get("/auth/external-identities/telegram/status")
async def telegram_linking_status(session: SessionData = Depends(current_session)):
    _require_user(session)
    return {
        "enabled": settings.telegram_enabled and settings.telegram_role_linking_enabled,
        "public_bot_enabled": settings.telegram_enabled and settings.telegram_public_bot_enabled,
        "transport": settings.telegram_transport,
        "admin_second_approval": settings.telegram_admin_second_approval,
    }


@router.post("/auth/external-identities/telegram/link-request", dependencies=[Depends(require_csrf)])
async def telegram_link_request(
    payload: LinkRequestInput,
    session: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    user = _require_user(session)
    if not settings.telegram_enabled or not settings.telegram_role_linking_enabled:
        raise HTTPException(status_code=409, detail="telegram_linking_disabled")
    if not verify_pw(payload.password, user.password_hash):
        raise HTTPException(status_code=403, detail="reauthentication_failed")
    code, request = await create_link_request(db, user)
    return {"code": code, "expires_at": request.expires_at, "command": f"/vincular {code}"}


@router.get("/auth/me/external-identities")
async def my_external_identities(
    session: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    user = _require_user(session)
    rows = (await db.scalars(select(ExternalIdentity).where(ExternalIdentity.user_id == user.id))).all()
    return [{"id": item.id, "provider": item.provider, "masked_identifier": masked_identity(item), "status": item.status, "created_at": item.created_at} for item in rows]


@router.delete("/auth/me/external-identities/{identity_id}", dependencies=[Depends(require_csrf)])
async def delete_my_external_identity(
    identity_id: int,
    session: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    user = _require_user(session)
    identity = await db.get(ExternalIdentity, identity_id)
    if not identity or identity.user_id != user.id:
        raise HTTPException(status_code=404, detail="external_identity_not_found")
    await revoke_identity(db, identity, user.id)
    return {"status": "revoked"}


@router.get("/admin/external-identities", dependencies=[Depends(require_roles("admin"))])
async def list_external_identities(db: AsyncSession = Depends(get_session)):
    rows = (await db.scalars(select(ExternalIdentity).order_by(ExternalIdentity.created_at.desc()))).all()
    return [{"id": item.id, "provider": item.provider, "masked_identifier": masked_identity(item), "user_id": item.user_id, "status": item.status, "last_seen_at": item.last_seen_at} for item in rows]


@router.post("/admin/external-identities/{identity_id}/approve", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def approve_external_identity(
    identity_id: int,
    session: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    admin = _require_user(session)
    identity = await db.get(ExternalIdentity, identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail="external_identity_not_found")
    if identity.user_id == admin.id:
        raise HTTPException(status_code=409, detail="self_approval_forbidden")
    target = await db.get(User, identity.user_id) if identity.user_id else None
    if not target or target.role != "admin" or identity.status != "pending_approval":
        raise HTTPException(status_code=409, detail="identity_not_pending_admin_approval")
    identity.status = "active"
    identity.approved_by_user_id = admin.id
    identity.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "active"}


@router.post("/admin/external-identities/{identity_id}/revoke", dependencies=[Depends(require_csrf), Depends(require_roles("admin"))])
async def admin_revoke_external_identity(
    identity_id: int,
    session: SessionData = Depends(current_session),
    db: AsyncSession = Depends(get_session),
):
    admin = _require_user(session)
    identity = await db.get(ExternalIdentity, identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail="external_identity_not_found")
    await revoke_identity(db, identity, admin.id)
    return {"status": "revoked"}
