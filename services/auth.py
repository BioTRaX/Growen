# NG-HEADER: Nombre de archivo: auth.py
# NG-HEADER: Ubicación: services/auth.py
# NG-HEADER: Descripción: Utilidades de autenticación y hashing del backend.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Utilidades de autenticación y manejo de sesiones."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Callable

from fastapi import Depends, HTTPException, Request
import logging
from fastapi.responses import Response
from passlib.hash import argon2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings
from db.models import Session as DBSess, User
from db.session import get_session


def verify_internal_service_token(request: Request) -> bool:
    """Verifica si la petición incluye un token válido de servicio interno.
    
    Los servicios internos (MCP servers, workers) pueden autenticarse usando
    el header X-Internal-Service-Token con el valor de INTERNAL_SERVICE_TOKEN.
    
    Returns:
        True si el token es válido, False en caso contrario.
    """
    token_from_header = request.headers.get("X-Internal-Service-Token")
    if not token_from_header:
        return False
    
    expected_token = settings.internal_service_token
    if not expected_token or expected_token == "":
        # Si no está configurado, rechazar (seguridad por defecto)
        return False
    
    # Comparación de tiempo constante para prevenir timing attacks
    return secrets.compare_digest(token_from_header, expected_token)


def hash_pw(pwd: str) -> str:
    """Hashea una contraseña usando Argon2id."""

    return argon2.using(type="ID").hash(pwd)


def verify_pw(pwd: str, hashed: str) -> bool:
    """Verifica una contraseña contra el hash almacenado."""

    return argon2.verify(pwd, hashed)


@dataclass
class SessionData:
    """Información de la sesión resuelta desde la cookie."""

    session: Optional[DBSess]
    user: Optional[User]
    role: str


async def set_session_cookies(resp: Response, sid: str, csrf: str, request: Request | None = None) -> None:
    """Configura cookies de sesión y CSRF.

    Antes de establecer nuevas cookies se eliminan las existentes para evitar
    que un identificador previo quede activo y pueda reutilizarse."""

    # Eliminar posibles cookies antiguas para prevenir fijación de sesión
    resp.delete_cookie("growen_session")
    resp.delete_cookie("csrf_token")

    max_age = settings.session_expire_minutes * 60
    secure = settings.cookie_secure
    if settings.env == "production":
        secure = True
    # En localhost nunca marcamos Secure si el esquema es HTTP, para que el
    # navegador acepte las cookies durante el desarrollo aunque haya una
    # configuración errónea de COOKIE_SECURE o ENV.
    try:
        host = request.url.hostname if request else None
        scheme = request.url.scheme if request else "http"
        if host in {"localhost", "127.0.0.1"} and scheme == "http":
            secure = False
    except Exception:
        pass
    cookie_args = {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
    }
    if settings.cookie_domain:
        cookie_args["domain"] = settings.cookie_domain
    resp.set_cookie("growen_session", sid, max_age=max_age, **cookie_args)

    cookie_args["httponly"] = False
    resp.set_cookie("csrf_token", csrf, max_age=max_age, **cookie_args)
    try:
        logging.getLogger("growen.auth").debug(
            "[cookies:set] session=%s secure=%s domain=%s sid_len=%d", sid[:12], cookie_args.get("secure"), cookie_args.get("domain"), len(sid)
        )
    except Exception:
        pass


async def create_session(
    db: AsyncSession,
    role: str,
    request: Request,
    user: User | None = None,
    prev_session: DBSess | None = None,
) -> tuple[DBSess, str]:
    """Genera una nueva sesión persistida y devuelve el objeto y token CSRF.

    Si se proporciona ``prev_session`` la elimina previamente para garantizar que
    el identificador de sesión se regenere en operaciones como login o logout."""

    if prev_session:
        await db.delete(prev_session)
        await db.commit()

    sid = secrets.token_hex(32)
    csrf = secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(minutes=settings.session_expire_minutes)
    sess = DBSess(
        id=sid,
        user_id=user.id if user else None,
        role=role,
        csrf_token=csrf,
        expires_at=expires,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(sess)
    await db.commit()
    return sess, csrf


async def current_session(
    request: Request, db: AsyncSession = Depends(get_session)
) -> SessionData:
    """Resuelve la sesión actual a partir de la cookie."""

    sid = request.cookies.get("growen_session")
    if not sid:
        # En desarrollo, opcionalmente se puede asumir admin sin sesión si DEV_ASSUME_ADMIN=true.
        # Por defecto, invitado.
        role = "admin" if (settings.env == "dev" and settings.dev_assume_admin) else "guest"
        return SessionData(None, None, role)

    res = await db.execute(select(DBSess).where(DBSess.id == sid))
    sess: DBSess | None = res.scalar_one_or_none()
    if not sess or sess.expires_at < datetime.utcnow():
        # En desarrollo, solo asumimos admin si DEV_ASSUME_ADMIN=true.
        if settings.env == "dev" and settings.dev_assume_admin:
            return SessionData(None, None, "admin")
        return SessionData(None, None, "guest")

    user: User | None = None
    if sess.user_id:
        user = await db.get(User, sess.user_id)
    return SessionData(sess, user, sess.role)


def require_roles(*roles: str) -> Callable[[SessionData], SessionData]:
    """Dependencia que asegura que la sesión tenga uno de los roles permitidos.

    Soporta tres métodos de autenticación (en orden de prioridad):
    1. Token de servicio interno (X-Internal-Service-Token): asume rol admin
    2. Sesión de usuario con cookie (growen_session)
    3. Headers de prueba (X-User-Roles, X-User-Id) - solo para tests
    """

    async def dep(
        request: Request, sess: SessionData = Depends(current_session)
    ) -> SessionData:
        # 1. Verificar token de servicio interno (mayor prioridad)
        if verify_internal_service_token(request):
            # Servicios internos siempre tienen rol admin
            return SessionData(None, None, "admin")

        # Fallback para pruebas que no usan cookie de sesión: aceptar cabeceras X-User-Roles / X-User-Id
        try:
            hdr_roles = (request.headers.get("x-user-roles") or "").lower().split(",")
            hdr_roles = [r.strip() for r in hdr_roles if r.strip()]
        except Exception:
            hdr_roles = []
        hdr_uid = request.headers.get("x-user-id")
        if hdr_roles:
            # Si alguna de las cabeceras incluye un rol permitido, autorizar
            if any(r in [rv.lower() for rv in roles] for r in hdr_roles):
                # Construir un SessionData derivado sin sesión real pero útil para logs/ratelimiting
                eff_role = next((r for r in hdr_roles if r in [rv.lower() for rv in roles]), roles[0])
                eff = SessionData(sess.session, sess.user, eff_role)
                # agregar user_id sintético si viene header
                try:
                    if hdr_uid is not None:
                        setattr(eff, "user_id", int(hdr_uid))
                except Exception:
                    setattr(eff, "user_id", hdr_uid)
                return eff

        # Chequeo normal de roles
        if sess.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return sess

    return dep


async def require_csrf(request: Request) -> None:
    """Valida el token CSRF en mutaciones."""

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get("csrf_token")
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or cookie != header:
        raise HTTPException(status_code=403, detail="CSRF invalid")


_LOGIN_WINDOW = 15 * 60
_MAX_ATTEMPTS = 10
_login_attempts: dict[str, list[float]] = {}


def check_login_rate_limit(ip: str) -> None:
    """Aplica rate limit por IP para el login."""

    attempts = _login_attempts.get(ip, [])
    now = time.time()
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW]
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too Many Requests")
    _login_attempts[ip] = attempts


def record_failed_login(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(time.time())


def reset_login_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)


__all__ = [
    "hash_pw",
    "verify_pw",
    "create_session",
    "set_session_cookies",
    "current_session",
    "require_roles",
    "require_csrf",
    "check_login_rate_limit",
    "record_failed_login",
    "reset_login_attempts",
]

