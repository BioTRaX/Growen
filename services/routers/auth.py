"""Endpoints de autenticación y gestión de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import secrets

from agent_core.config import settings
from db.models import User, PasswordResetToken
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


@router.post("/login")
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_session)):
    ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(ip)

    stmt = select(User).where(
        or_(User.identifier == payload.identifier, User.email == payload.identifier)
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user or not verify_pw(payload.password, user.password_hash):
        record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    reset_login_attempts(ip)
    sess, csrf = await create_session(db, user.role, request, user)
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
    await set_session_cookies(resp, sess.id, csrf)
    return resp


@router.post("/guest")
async def login_guest(request: Request, db: AsyncSession = Depends(get_session)):
    sess, csrf = await create_session(db, "guest", request)
    resp = JSONResponse({"role": "guest"})
    await set_session_cookies(resp, sess.id, csrf)
    return resp


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(request: Request, db: AsyncSession = Depends(get_session)):
    sess = await current_session(request, db)
    if sess.session:
        await db.delete(sess.session)
        await db.commit()
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("growen_session")
    resp.delete_cookie("csrf_token")
    return resp


@router.get("/me")
async def me(sess: SessionData = Depends(current_session)):
    if not sess.session:
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
    password: str | None = None
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


class PasswordResetOut(BaseModel):
    token: str
    expires_at: datetime


class PasswordResetIn(BaseModel):
    password: str


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def create_password_reset(
    user_id: int, db: AsyncSession = Depends(get_session)
) -> PasswordResetOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(
        minutes=settings.password_reset_token_minutes
    )
    prt = PasswordResetToken(
        token=token, user_fk=user.id, expires_at=expires, used=False
    )
    db.add(prt)
    await db.commit()
    return PasswordResetOut(token=token, expires_at=expires)


@router.post("/reset/{token}")
async def reset_password(
    token: str, payload: PasswordResetIn, db: AsyncSession = Depends(get_session)
):
    stmt = select(PasswordResetToken).where(PasswordResetToken.token == token)
    res = await db.execute(stmt)
    prt = res.scalar_one_or_none()
    if not prt or prt.used or prt.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token inválido")
    user = await db.get(User, prt.user_fk)
    if not user:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    user.password_hash = hash_pw(payload.password)
    prt.used = True
    await db.commit()
    return {"status": "ok"}


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
    if payload.password is not None:
        user.password_hash = hash_pw(payload.password)
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

