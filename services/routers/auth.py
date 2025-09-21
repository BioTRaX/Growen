# NG-HEADER: Nombre de archivo: auth.py
# NG-HEADER: Ubicación: services/routers/auth.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints de autenticación y gestión de usuarios."""

import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, ServiceLog
import socket
from db.session import get_session
from services.auth import (
    hash_pw,
    verify_pw,
    create_session,
    set_session_cookies,
    current_session,
    require_roles,
    require_csrf,
    check_login_rate_limit,
    record_failed_login,
    reset_login_attempts,
    SessionData,
)


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    identifier: str
    password: str


logger = logging.getLogger("growen.auth")

@router.post("/login")
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_session)):
    t0 = secrets.token_hex(4)
    logger.debug("[login:start] tag=%s ip=%s identifier=%s", t0, request.client.host if request.client else None, payload.identifier)
    ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(ip)

    ident = (payload.identifier or "").strip()
    stmt = select(User).where(
        or_(
            func.lower(User.identifier) == ident.lower(),
            func.lower(User.email) == ident.lower(),
        )
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        logger.debug("[login:not_found] tag=%s identifier=%s", t0, ident)
    if user and not verify_pw(payload.password, user.password_hash):
        logger.debug("[login:bad_password] tag=%s user_id=%s", t0, user.id)
    if not user or not verify_pw(payload.password, user.password_hash):
        record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    reset_login_attempts(ip)
    prev = await current_session(request, db)
    sess, csrf = await create_session(
        db, user.role, request, user, prev_session=prev.session
    )
    resp = JSONResponse(
        {
            "id": user.id,
            "identifier": user.identifier,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "supplier_id": user.supplier_id,
        }
    )
    await set_session_cookies(resp, sess.id, csrf, request)
    logger.debug("[login:ok] tag=%s user_id=%s role=%s session=%s", t0, user.id, user.role, sess.id[:12])
    return resp


@router.post("/guest")
async def login_guest(request: Request, db: AsyncSession = Depends(get_session)):
    t0 = secrets.token_hex(4)
    logger.debug("[guest:start] tag=%s ip=%s", t0, request.client.host if request.client else None)
    prev = await current_session(request, db)
    sess, csrf = await create_session(
        db, "guest", request, prev_session=prev.session
    )
    resp = JSONResponse({"role": "guest"})
    await set_session_cookies(resp, sess.id, csrf, request)
    logger.debug("[guest:ok] tag=%s session=%s", t0, sess.id[:12])
    return resp


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(request: Request, db: AsyncSession = Depends(get_session)):
    prev = await current_session(request, db)
    new_sess, csrf = await create_session(
        db, "guest", request, prev_session=prev.session
    )
    resp = JSONResponse({"status": "ok"})
    await set_session_cookies(resp, new_sess.id, csrf, request)
    return resp


@router.get("/me")
async def me(sess: SessionData = Depends(current_session)):
    # En desarrollo, si no hay sesión persistida pero el resolvedor asignó un rol
    # elevado (admin/colaborador), reflejamos autenticado para no bloquear el FE.
    if not sess.session:
        from agent_core.config import settings as _settings
        if _settings.env == "dev" and sess.role in ("admin", "colaborador"):
            return {"is_authenticated": True, "role": sess.role}
        return {"is_authenticated": False, "role": "guest"}
    data = {"is_authenticated": True, "role": sess.role}
    if sess.user:
        data["user"] = {
            "id": sess.user.id,
            "identifier": sess.user.identifier,
            "email": sess.user.email,
            "name": sess.user.name,
            "role": sess.user.role,
            "supplier_id": sess.user.supplier_id,
        }
    return data


class UserCreate(BaseModel):
    identifier: str
    email: str | None = None
    name: str | None = None
    password: str
    role: str
    supplier_id: int | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    role: str | None = None
    supplier_id: int | None = None


@router.get("/users", dependencies=[Depends(require_roles("admin"))])
async def list_users(
    q: str = "",
    role: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_session),
):
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                User.identifier.ilike(like),
                User.email.ilike(like),
                User.name.ilike(like),
            )
        )
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    users = [
        {
            "id": u.id,
            "identifier": u.identifier,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "supplier_id": u.supplier_id,
        }
        for u in res.scalars().all()
    ]
    return users


@router.post(
    "/users",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_session)):
    user = User(
        identifier=payload.identifier,
        email=payload.email,
        name=payload.name,
        password_hash=hash_pw(payload.password),
        role=payload.role,
        supplier_id=payload.supplier_id,
    )
    db.add(user)
    await db.commit()
    return {
        "id": user.id,
        "identifier": user.identifier,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "supplier_id": user.supplier_id,
    }


@router.patch(
    "/users/{user_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def update_user(
    user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_session)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if payload.email is not None:
        user.email = payload.email
    if payload.name is not None:
        user.name = payload.name
    if payload.role is not None:
        user.role = payload.role
    if payload.supplier_id is not None:
        user.supplier_id = payload.supplier_id
    await db.commit()
    return {
        "id": user.id,
        "identifier": user.identifier,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "supplier_id": user.supplier_id,
    }


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def reset_password(user_id: int, db: AsyncSession = Depends(get_session)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    new_password = secrets.token_urlsafe(8)
    user.password_hash = hash_pw(new_password)
    await db.commit()
    return {"password": new_password}


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_session)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    ident = user.identifier
    db.delete(user)
    await db.flush()
    # Audit log via service_logs
    try:
        db.add(ServiceLog(service="users", correlation_id=secrets.token_hex(8), action="delete", host=socket.gethostname(), pid=None, duration_ms=None, ok=True, level="INFO", error=None, payload={"user": ident, "user_id": user_id}))
    except Exception:
        pass
    await db.commit()
    return {"status": "ok"}


# --- Debug endpoints (solo entorno dev) ---
@router.get("/debug/current")
async def debug_current(sess: SessionData = Depends(current_session)):
    """Devuelve la sesión cruda (solo dev)."""
    from agent_core.config import settings as _s
    if _s.env != "dev":
        raise HTTPException(status_code=404)
    out = {"role": sess.role, "has_session": bool(sess.session)}
    if sess.session:
        out["session"] = {
            "id": sess.session.id,
            "user_id": sess.session.user_id,
            "expires_at": sess.session.expires_at.isoformat() if sess.session.expires_at else None,
        }
    if sess.user:
        out["user"] = {"id": sess.user.id, "identifier": sess.user.identifier, "role": sess.user.role}
    return out


@router.get("/debug/sessions")
async def debug_sessions(db: AsyncSession = Depends(get_session)):
    """Lista sesiones activas (solo dev): id, user, rol, expira."""
    from agent_core.config import settings as _s
    if _s.env != "dev":
        raise HTTPException(status_code=404)
    from sqlalchemy import select
    from db.models import Session as DBSess, User as DBUser
    rows = []
    res = await db.execute(select(DBSess))
    for s in res.scalars().all():
        u_ident = None
        if s.user_id:
            u = await db.get(DBUser, s.user_id)
            if u:
                u_ident = u.identifier
        rows.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_identifier": u_ident,
            "role": s.role,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        })
    return {"count": len(rows), "items": rows}

