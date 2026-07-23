#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: security.py
# NG-HEADER: Ubicación: mcp_servers/security.py
# NG-HEADER: Descripción: Autenticación, autorización, rate limiting y contexto común para MCP.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable

import jwt
import redis.asyncio as redis
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - las imágenes reciben env desde Docker
    pass


class MCPAuthError(Exception):
    """Error base de autenticación o autorización MCP."""


class MCPTokenExpired(MCPAuthError):
    """El token expiró."""


class MCPTokenInvalid(MCPAuthError):
    """El token no es válido."""


class MCPUnauthorized(MCPAuthError):
    """El rol no puede ejecutar la herramienta."""


class MCPRateLimited(MCPAuthError):
    """El sujeto superó el límite de invocaciones."""


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    role: str
    exp: float
    iss: str
    aud: str
    jti: str
    iat: float
    channel: str = "web"


_current_token: ContextVar[str | None] = ContextVar("mcp_token", default=None)
_current_claims: ContextVar[TokenClaims | None] = ContextVar("mcp_claims", default=None)
_current_request_id: ContextVar[str | None] = ContextVar("mcp_request_id", default=None)
_rate_windows: Dict[str, list[float]] = defaultdict(list)
_audit_logger = logging.getLogger("growen.mcp.audit")


def _redis_url() -> str:
    return os.getenv("MCP_RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _redis_key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"growen:mcp:{kind}:{digest}"


def _secret() -> str:
    value = os.getenv("MCP_SECRET_KEY", "")
    if value:
        return value
    raise MCPTokenInvalid("MCP_SECRET_KEY no configurado")


def _candidate_secrets(token: str) -> list[str]:
    current = _secret()
    previous = os.getenv("MCP_SECRET_KEY_PREVIOUS", "")
    expected_kid = os.getenv("MCP_JWT_KEY_ID", "")
    previous_kid = os.getenv("MCP_JWT_PREVIOUS_KEY_ID", "")
    try:
        token_kid = str(jwt.get_unverified_header(token).get("kid") or "")
    except jwt.InvalidTokenError as exc:
        raise MCPTokenInvalid("Header JWT MCP inválido") from exc
    if token_kid and expected_kid and token_kid == expected_kid:
        return [current]
    if token_kid and previous and previous_kid and token_kid == previous_kid:
        return [previous]
    if token_kid and (expected_kid or previous_kid):
        raise MCPTokenInvalid("kid MCP desconocido")
    return [current]


def _issuer() -> str:
    return os.getenv("MCP_JWT_ISSUER", "growen-api")


def _audience() -> str:
    return os.getenv("MCP_JWT_AUDIENCE", "growen-mcp")


def mcp_transport_security(service_hosts: Iterable[str]) -> TransportSecuritySettings:
    """Activa protección DNS rebinding con hosts locales y de Compose explícitos."""
    configured_hosts = [
        item.strip() for item in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if item.strip()
    ]
    configured_origins = [
        item.strip() for item in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",") if item.strip()
    ]
    allowed_hosts = configured_hosts or [
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "[::1]",
        "[::1]:*",
        *service_hosts,
    ]
    allowed_origins = configured_origins or [
        "http://127.0.0.1:*",
        "http://localhost:*",
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def verify_mcp_token(token: str) -> TokenClaims:
    payload = None
    last_error: Exception | None = None
    for secret in _candidate_secrets(token):
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                issuer=_issuer(),
                audience=_audience(),
                options={"require": ["sub", "role", "iat", "exp", "iss", "aud", "jti"]},
            )
            break
        except jwt.ExpiredSignatureError as exc:
            raise MCPTokenExpired("Token MCP expirado") from exc
        except jwt.InvalidTokenError as exc:
            last_error = exc
    if payload is None:
        raise MCPTokenInvalid("Token MCP inválido") from last_error

    issued_at = float(payload["iat"])
    expires_at = float(payload["exp"])
    max_ttl = max(60, int(os.getenv("MCP_JWT_MAX_TTL_SECONDS", "600")))
    if expires_at - issued_at > max_ttl:
        raise MCPTokenInvalid("TTL MCP excede el máximo permitido")

    return TokenClaims(
        sub=str(payload["sub"]),
        role=str(payload["role"]),
        exp=float(payload["exp"]),
        iss=str(payload["iss"]),
        aud=str(payload["aud"]),
        jti=str(payload["jti"]),
        iat=issued_at,
        channel=str(payload.get("channel") or "web"),
    )


def get_current_token() -> str:
    token = _current_token.get()
    if not token:
        raise MCPTokenInvalid("No hay token MCP asociado a la solicitud")
    return token


def get_current_claims() -> TokenClaims:
    claims = _current_claims.get()
    if not claims:
        raise MCPTokenInvalid("No hay claims MCP asociados a la solicitud")
    return claims


async def check_rate_limit(user_id: str) -> bool:
    limit = max(1, int(os.getenv("MCP_RATE_LIMIT_PER_MINUTE", "60")))
    backend = os.getenv("MCP_RATE_LIMIT_BACKEND", "memory").lower()
    if backend == "redis":
        client = redis.from_url(_redis_url(), decode_responses=True)
        key = _redis_key("rate", f"{_issuer()}:{_audience()}:{user_id}")
        try:
            value = await client.incr(key)
            if value == 1:
                await client.expire(key, 60)
            return int(value) <= limit
        except Exception as exc:
            _audit_logger.error("rate_limit_backend_error type=%s", type(exc).__name__)
            return False
        finally:
            await client.aclose()

    now = time.time()
    _rate_windows[user_id] = [stamp for stamp in _rate_windows[user_id] if now - stamp < 60]
    if len(_rate_windows[user_id]) >= limit:
        return False
    _rate_windows[user_id].append(now)
    return True


async def is_jti_revoked(jti: str) -> bool:
    if os.getenv("MCP_TOKEN_REVOCATION_BACKEND", "none").lower() != "redis":
        return False
    client = redis.from_url(_redis_url(), decode_responses=True)
    try:
        return bool(await client.exists(_redis_key("revoked", jti)))
    except Exception as exc:
        _audit_logger.error("revocation_backend_error type=%s", type(exc).__name__)
        return True
    finally:
        await client.aclose()


async def revoke_jti(jti: str, expires_at: float) -> None:
    """Revoca un token hasta su expiración natural sin persistir el JTI en claro."""
    if os.getenv("MCP_TOKEN_REVOCATION_BACKEND", "none").lower() != "redis":
        raise RuntimeError("La revocación MCP requiere MCP_TOKEN_REVOCATION_BACKEND=redis")
    ttl = max(1, int(expires_at - time.time()))
    client = redis.from_url(_redis_url(), decode_responses=True)
    try:
        await client.set(_redis_key("revoked", jti), "1", ex=ttl)
    except Exception as exc:
        _audit_logger.error("revocation_write_error type=%s", type(exc).__name__)
        raise RuntimeError("No se pudo registrar la revocación MCP") from exc
    finally:
        await client.aclose()


def reset_rate_limit(user_id: str | None = None) -> None:
    if user_id is None:
        _rate_windows.clear()
    else:
        _rate_windows.pop(user_id, None)


def log_audit(
    user_id: str,
    tool_name: str,
    status: str,
    execution_time_ms: float | None = None,
    error_code: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "subject_hash": hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16],
        "tool_name": tool_name,
        "status": status,
    }
    if execution_time_ms is not None:
        entry["execution_time_ms"] = round(execution_time_ms, 2)
    if error_code:
        entry["error_code"] = error_code
    request_id = _current_request_id.get()
    if request_id:
        entry["request_id"] = request_id
    claims = _current_claims.get()
    if claims:
        entry["jti_hash"] = hashlib.sha256(claims.jti.encode("utf-8")).hexdigest()[:16]
    _audit_logger.info(json.dumps(entry, ensure_ascii=False, sort_keys=True))


def require_mcp_auth(allowed_roles: Iterable[str] | None = None):
    roles = set(allowed_roles or [])

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(token: str, **kwargs) -> Dict[str, Any]:
            started = time.perf_counter()
            claims = verify_mcp_token(token)
            if await is_jti_revoked(claims.jti):
                log_audit(claims.sub, func.__name__, "revoked")
                raise MCPTokenInvalid("Token MCP revocado")
            if not await check_rate_limit(claims.sub):
                log_audit(claims.sub, func.__name__, "rate_limited")
                raise MCPRateLimited("Límite de invocaciones MCP excedido")
            if roles and claims.role not in roles:
                log_audit(claims.sub, func.__name__, "unauthorized")
                raise MCPUnauthorized("Rol no autorizado para esta herramienta")
            token_ctx = _current_token.set(token)
            claims_ctx = _current_claims.set(claims)
            try:
                result = await func(**kwargs)
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                log_audit(claims.sub, func.__name__, "error", elapsed, type(exc).__name__)
                raise
            finally:
                _current_claims.reset(claims_ctx)
                _current_token.reset(token_ctx)
            elapsed = (time.perf_counter() - started) * 1000
            log_audit(claims.sub, func.__name__, "success", elapsed)
            return result

        return wrapper

    return decorator


class MCPBearerContextMiddleware:
    """Valida Bearer JWT antes de entregar solicitudes al endpoint `/mcp`."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope.get("type") != "http" or not (path == "/mcp" or path.startswith("/mcp/")):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        if not authorization.lower().startswith("bearer "):
            await JSONResponse({"error": "mcp_token_required"}, status_code=401)(scope, receive, send)
            return

        token = authorization.split(" ", 1)[1].strip()
        try:
            claims = verify_mcp_token(token)
            if await is_jti_revoked(claims.jti):
                raise MCPTokenInvalid("Token MCP revocado")
        except MCPAuthError:
            await JSONResponse({"error": "mcp_token_invalid"}, status_code=401)(scope, receive, send)
            return

        token_ctx = _current_token.set(token)
        claims_ctx = _current_claims.set(claims)
        request_id_header = headers.get(b"x-request-id", b"").decode("latin-1")[:128]
        request_ctx = _current_request_id.set(request_id_header or str(uuid.uuid4()))
        try:
            await self.app(scope, receive, send)
        finally:
            _current_request_id.reset(request_ctx)
            _current_token.reset(token_ctx)
            _current_claims.reset(claims_ctx)


__all__ = [
    "MCPAuthError",
    "MCPTokenExpired",
    "MCPTokenInvalid",
    "MCPUnauthorized",
    "MCPRateLimited",
    "TokenClaims",
    "MCPBearerContextMiddleware",
    "verify_mcp_token",
    "get_current_token",
    "get_current_claims",
    "check_rate_limit",
    "is_jti_revoked",
    "revoke_jti",
    "reset_rate_limit",
    "log_audit",
    "require_mcp_auth",
    "mcp_transport_security",
]
