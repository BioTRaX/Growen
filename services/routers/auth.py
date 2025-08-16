"""Endpoints de autenticación y gestión de usuarios."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
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
    email: str
    password: str


@router.post("/login")
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_session)):
    ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(ip)

    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not verify_pw(payload.password, user.password_hash):
        record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    reset_login_attempts(ip)
    sess, csrf = await create_session(db, user.role, request, user)
    resp = JSONResponse(
        {
            "id": user.id,
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
            "email": sess.user.email,
            "name": sess.user.name,
            "role": sess.user.role,
            "supplier_id": sess.user.supplier_id,
        }
    return data


class RegisterIn(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str
    supplier_id: int | None = None


@router.post(
    "/register",
    dependencies=[Depends(require_csrf), Depends(require_roles("admin"))],
)
async def register_user(
    payload: RegisterIn, db: AsyncSession = Depends(get_session)
):
    user = User(
        email=payload.email,
        password_hash=hash_pw(payload.password),
        name=payload.name,
        role=payload.role,
        supplier_id=payload.supplier_id,
    )
    db.add(user)
    await db.commit()
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "supplier_id": user.supplier_id,
    }

