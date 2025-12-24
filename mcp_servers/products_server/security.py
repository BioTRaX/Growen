#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: security.py
# NG-HEADER: Ubicación: mcp_servers/products_server/security.py
# NG-HEADER: Descripción: Módulo de seguridad MCP con validación JWT, rate limiting y auditoría
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""MCP Products Server Security Module.

Proporciona validación de tokens JWT, autorización basada en roles,
rate limiting en memoria y logging estructurado de auditoría.
"""
from __future__ import annotations

import functools
import time
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Set
from collections import defaultdict

import jwt

# --- Configuración ---
def _get_mcp_secret() -> str:
    """Obtiene la clave secreta para JWT desde variables de entorno."""
    return os.getenv("MCP_SECRET_KEY", "")


def _get_rate_limit() -> int:
    """Obtiene el límite de peticiones por minuto."""
    return int(os.getenv("MCP_RATE_LIMIT_PER_MINUTE", "60"))


# --- Excepciones ---
class MCPAuthError(Exception):
    """Error base de autenticación/autorización MCP."""


class MCPTokenExpired(MCPAuthError):
    """El token ha expirado."""


class MCPTokenInvalid(MCPAuthError):
    """Firma de token inválida o token malformado."""


class MCPUnauthorized(MCPAuthError):
    """Rol de usuario no autorizado para esta operación."""


class MCPRateLimited(MCPAuthError):
    """Demasiadas peticiones de este usuario."""


# --- Token Claims ---
@dataclass
class TokenClaims:
    """Datos extraídos de un token JWT validado."""
    sub: str
    role: str
    exp: float
    jti: str | None = None


# --- Validación de Token ---
def verify_mcp_token(token: str) -> TokenClaims:
    """Valida un token JWT y extrae sus claims.
    
    Args:
        token: Token JWT a validar.
        
    Returns:
        TokenClaims con los datos del usuario.
        
    Raises:
        MCPTokenInvalid: Si el token es inválido o la firma no coincide.
        MCPTokenExpired: Si el token ha expirado.
    """
    secret = _get_mcp_secret()
    if not secret:
        raise MCPTokenInvalid("MCP_SECRET_KEY not configured")
    
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return TokenClaims(
            sub=payload.get("sub", "unknown"),
            role=payload.get("role", "guest"),
            exp=payload.get("exp", 0),
            jti=payload.get("jti"),
        )
    except jwt.ExpiredSignatureError:
        raise MCPTokenExpired("Token expired")
    except jwt.InvalidTokenError as e:
        raise MCPTokenInvalid(f"Invalid token: {e}")


# --- Rate Limiting (Fixed Window) ---
_rate_windows: Dict[str, list[float]] = defaultdict(list)


def check_rate_limit(user_id: str) -> bool:
    """Verifica si el usuario puede realizar una petición.
    
    Implementa un rate limiter de ventana fija (fixed window).
    
    Args:
        user_id: Identificador del usuario (sub del token).
        
    Returns:
        True si la petición está permitida, False si excede el límite.
    """
    limit = _get_rate_limit()
    window = 60.0  # 1 minuto
    now = time.time()
    
    # Limpiar entradas antiguas
    _rate_windows[user_id] = [t for t in _rate_windows[user_id] if now - t < window]
    
    if len(_rate_windows[user_id]) >= limit:
        return False
    
    _rate_windows[user_id].append(now)
    return True


def reset_rate_limit(user_id: str | None = None) -> None:
    """Resetea el rate limit (útil para tests).
    
    Args:
        user_id: Si se especifica, resetea solo ese usuario. Si es None, resetea todos.
    """
    if user_id is None:
        _rate_windows.clear()
    else:
        _rate_windows.pop(user_id, None)


# --- Audit Logger ---
_audit_logger = logging.getLogger("mcp_products.audit")


def log_audit(
    user_id: str,
    tool_name: str,
    status: str,
    execution_time_ms: float | None = None,
    error: str | None = None,
) -> None:
    """Registra una entrada de auditoría estructurada.
    
    Args:
        user_id: Identificador del usuario.
        tool_name: Nombre de la herramienta invocada.
        status: Estado de la operación (success, blocked, rate_limited, unauthorized, error).
        execution_time_ms: Tiempo de ejecución en milisegundos.
        error: Descripción del error si aplica.
    """
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_id": user_id,
        "tool_name": tool_name,
        "status": status,
    }
    if execution_time_ms is not None:
        entry["execution_time_ms"] = round(execution_time_ms, 2)
    if error:
        entry["error"] = error
    _audit_logger.info(entry)


# --- Decorador de Seguridad ---
def require_mcp_auth(allowed_roles: Set[str] | list[str] | None = None):
    """Decorador para funciones de herramientas MCP que requieren autenticación.
    
    Valida el token JWT, verifica rate limiting, y controla acceso por rol.
    
    Args:
        allowed_roles: Conjunto de roles permitidos. Si es None o vacío,
                      cualquier usuario autenticado puede acceder.
    
    Usage:
        @require_mcp_auth(allowed_roles=["admin", "colaborador"])
        async def my_tool(sku: str = None, **kwargs):
            # token ya fue validado, ejecutar lógica
            ...
    
    La función decorada recibe `token` como primer parámetro (string),
    que es removido antes de llamar a la función original.
    """
    if allowed_roles is None:
        allowed_roles = set()
    elif isinstance(allowed_roles, list):
        allowed_roles = set(allowed_roles)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(token: str, **kwargs) -> Dict[str, Any]:
            start = time.time()
            tool_name = func.__name__
            user_id = "unknown"
            
            try:
                # 1. Validar token
                claims = verify_mcp_token(token)
                user_id = claims.sub
                
                # 2. Verificar rate limit
                if not check_rate_limit(user_id):
                    log_audit(user_id, tool_name, "rate_limited")
                    raise MCPRateLimited(f"Rate limit exceeded for {user_id}")
                
                # 3. Verificar autorización por rol (si se especificaron roles)
                if allowed_roles and claims.role not in allowed_roles:
                    log_audit(
                        user_id, tool_name, "unauthorized",
                        error=f"Role {claims.role} not in {allowed_roles}"
                    )
                    raise MCPUnauthorized(
                        f"Role '{claims.role}' not authorized. Required: {allowed_roles}"
                    )
                
                # 4. Ejecutar herramienta
                result = await func(**kwargs)
                
                elapsed = (time.time() - start) * 1000
                log_audit(user_id, tool_name, "success", elapsed)
                return result
                
            except MCPAuthError:
                # Re-raise auth errors sin modificar
                raise
            except Exception as e:
                # Otros errores se loguean como error genérico
                elapsed = (time.time() - start) * 1000
                log_audit(user_id, tool_name, "error", elapsed, str(e))
                raise
            
        return wrapper
    return decorator


__all__ = [
    "MCPAuthError",
    "MCPTokenExpired",
    "MCPTokenInvalid",
    "MCPUnauthorized",
    "MCPRateLimited",
    "TokenClaims",
    "verify_mcp_token",
    "check_rate_limit",
    "reset_rate_limit",
    "log_audit",
    "require_mcp_auth",
]
