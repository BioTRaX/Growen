# NG-HEADER: Nombre de archivo: auth.py
# NG-HEADER: Ubicación: services/auth.py
# NG-HEADER: Descripción: Utilidades de autenticación y hashing del backend.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Utilidades de autenticación y manejo de sesiones."""

from __future__ import annotations

import secrets
import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable

from fastapi import Depends, HTTPException, Request, WebSocket
import jwt as pyjwt
import logging
from fastapi.responses import Response
from passlib.hash import argon2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.config import settings
from db.models import Session as DBSess, User
from db.session import get_session


def hash_session_id(session_id: str) -> str:
    """Representación irreversible almacenada en DB para reducir impacto de una fuga."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def resolve_internal_service(request: Request) -> tuple[str, str] | None:
    """Verifica si la petición incluye un token válido de servicio interno.
    
    Los servicios internos (MCP servers, workers) pueden autenticarse usando
    el header X-Internal-Service-Token con el valor de INTERNAL_SERVICE_TOKEN.
    
    Returns:
        True si el token es válido, False en caso contrario.
    """
    token_from_header = request.headers.get("X-Internal-Service-Token")
    service_name = request.headers.get("X-Internal-Service-Name")
    if not token_from_header or not service_name:
        return None
    
    expected_token = settings.internal_service_token
    if not expected_token:
        # Si no está configurado, rechazar (seguridad por defecto)
        return None
    if not secrets.compare_digest(service_name, settings.internal_service_name):
        return None
    
    # Comparación de tiempo constante para prevenir timing attacks
    if not secrets.compare_digest(token_from_header, expected_token):
        return None
    return service_name, settings.internal_service_role


def verify_internal_service_token(request: Request) -> bool:
    return resolve_internal_service(request) is not None


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
    host = request.url.hostname if request else None
    scheme = request.url.scheme if request else "http"
    if host in {"localhost", "127.0.0.1"} and scheme == "http":
        secure = False
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
    logging.getLogger("growen.auth").debug(
        "[cookies:set] secure=%s domain=%s", cookie_args.get("secure"), cookie_args.get("domain")
    )


async def create_session(
    db: AsyncSession,
    role: str,
    request: Request,
    user: User | None = None,
    prev_session: DBSess | None = None,
) -> tuple[DBSess, str, str]:
    """Genera una sesión y devuelve registro persistido, SID crudo y token CSRF.

    El SID crudo es el único valor que debe enviarse al navegador. En la base se
    conserva exclusivamente su hash para que una filtración no permita reutilizar
    sesiones activas.

    Si se proporciona ``prev_session`` la elimina previamente para garantizar que
    el identificador de sesión se regenere en operaciones como login o logout."""

    if prev_session:
        await db.delete(prev_session)
        await db.commit()

    sid = secrets.token_hex(32)
    csrf = secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(minutes=settings.session_expire_minutes)
    sess = DBSess(
        id=hash_session_id(sid),
        user_id=user.id if user else None,
        role=role,
        csrf_token=csrf,
        expires_at=expires,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(sess)
    await db.commit()
    return sess, sid, csrf


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

    res = await db.execute(select(DBSess).where(DBSess.id == hash_session_id(sid)))
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


async def current_websocket_session(websocket: WebSocket, db: AsyncSession) -> SessionData:
    """Resuelve una sesión WebSocket sin aceptar primero la conexión.

    Los WebSockets no ejecutan dependencias HTTP ni validación CSRF. La cookie
    HttpOnly de sesión es la credencial y se valida contra PostgreSQL antes de
    exponer estado operativo.
    """

    sid = websocket.cookies.get("growen_session")
    if not sid:
        if settings.env in {"test", "testing"}:
            roles = [value.strip().lower() for value in (websocket.headers.get("x-user-roles") or "").split(",")]
            role = next((value for value in roles if value), "guest")
            return SessionData(None, None, role)
        return SessionData(None, None, "guest")

    result = await db.execute(select(DBSess).where(DBSess.id == hash_session_id(sid)))
    session = result.scalar_one_or_none()
    if not session or session.expires_at < datetime.utcnow():
        return SessionData(None, None, "guest")
    user = await db.get(User, session.user_id) if session.user_id else None
    return SessionData(session, user, session.role)


async def require_websocket_roles(
    websocket: WebSocket,
    db: AsyncSession,
    *roles: str,
) -> SessionData:
    """Valida rol antes de aceptar un WebSocket administrativo."""

    session = await current_websocket_session(websocket, db)
    if session.role not in roles:
        await websocket.close(code=4403, reason="Forbidden")
        raise HTTPException(status_code=403, detail="Forbidden")
    return session


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
        internal_service = resolve_internal_service(request)
        if internal_service:
            service_name, service_role = internal_service
            if service_role in roles:
                service_session = SessionData(None, None, service_role)
                setattr(service_session, "service_name", service_name)
                return service_session

        # Fallback para pruebas que no usan cookie de sesión: aceptar cabeceras X-User-Roles / X-User-Id
        hdr_roles: list[str] = []
        hdr_uid = None
        if settings.env in {"test", "testing"}:
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


def create_mcp_token(
    sub: str,
    role: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict | None = None,
    audience: str | None = None,
) -> str:
    """Genera un JWT firmado para autenticación de servidores MCP.
    
    El token es firmado con MCP_SECRET_KEY (diferente de SECRET_KEY principal)
    y contiene claims de usuario para autorización en herramientas MCP.
    
    Args:
        sub: Identificador del sujeto (user_id, service_name, etc.)
        role: Rol del usuario (admin, colaborador, guest, etc.)
        expires_delta: Duración de validez del token. Por defecto: 5 minutos.
        extra_claims: Claims adicionales a incluir en el payload.
    
    Returns:
        Token JWT firmado como string.
        
    Raises:
        RuntimeError: Si MCP_SECRET_KEY no está configurado.
    """
    target_audience = audience or settings.mcp_jwt_audience
    if target_audience == settings.mcp_products_audience:
        secret = settings.mcp_products_secret_key
        key_id = settings.mcp_products_key_id
    elif target_audience == settings.mcp_web_search_audience:
        secret = settings.mcp_web_search_secret_key
        key_id = settings.mcp_web_search_key_id
    else:
        secret = settings.mcp_secret_key
        key_id = os.getenv("MCP_JWT_KEY_ID", "legacy-v1")
    if not secret:
        raise RuntimeError("MCP_SECRET_KEY no configurado; ejecutar bootstrap-dev.ps1")
    
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=5))
    
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": expires,
        "jti": secrets.token_hex(8),  # Identificador para auditoría y revocación futura
        "iss": settings.mcp_jwt_issuer,
        "aud": target_audience,
    }
    if extra_claims:
        reserved = {"sub", "role", "iat", "exp", "jti", "iss", "aud"}
        if reserved.intersection(extra_claims):
            raise ValueError("extra_claims no puede sobrescribir claims MCP reservados")
        payload.update(extra_claims)
    
    return pyjwt.encode(payload, secret, algorithm="HS256", headers={"kid": key_id})


__all__ = [
    "hash_pw",
    "verify_pw",
    "create_session",
    "set_session_cookies",
    "current_session",
    "require_roles",
    "require_csrf",
    "current_websocket_session",
    "require_websocket_roles",
    "check_login_rate_limit",
    "record_failed_login",
    "reset_login_attempts",
    "create_mcp_token",
]

