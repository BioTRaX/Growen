"""Configuración central del agente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Marcadores que deben sustituirse en producción
SECRET_KEY_PLACEHOLDER = "REEMPLAZAR_SECRET_KEY"
ADMIN_PASS_PLACEHOLDER = "REEMPLAZAR_ADMIN_PASS"

# Carga automática de variables definidas en .env
load_dotenv()


def _expand_local(origins: list[str]) -> list[str]:
    """Duplica ``localhost``/``127.0.0.1`` para evitar errores de CORS en desarrollo."""
    out: set[str] = set()
    for o in origins:
        o = o.strip()
        if not o:
            continue
        out.add(o)
        if o.startswith("http://localhost:"):
            out.add(o.replace("http://localhost:", "http://127.0.0.1:"))
        if o.startswith("http://127.0.0.1:"):
            out.add(o.replace("http://127.0.0.1:", "http://localhost:"))
    return list(out)


@dataclass
class Settings:
    """Parámetros de configuración leídos de variables de entorno."""

    env: str = os.getenv("ENV", "dev")
    db_url: str = os.getenv("DB_URL", "")
    ai_mode: str = os.getenv("AI_MODE", "auto")
    ai_allow_external: bool = os.getenv("AI_ALLOW_EXTERNAL", "true").lower() == "true"
    secret_key: str = os.getenv("SECRET_KEY", SECRET_KEY_PLACEHOLDER)
    admin_user: str = os.getenv("ADMIN_USER", "admin")
    admin_pass: str = os.getenv("ADMIN_PASS", ADMIN_PASS_PLACEHOLDER)
    session_expire_minutes: int = int(
        os.getenv("SESSION_EXPIRE_MINUTES", "1440")
    )  # duración de la sesión en minutos (1 día por defecto)
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    cookie_domain: str | None = os.getenv("COOKIE_DOMAIN") or None
    allowed_origins: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.db_url:
            raise RuntimeError("DB_URL debe definirse en el entorno")
        if self.secret_key == SECRET_KEY_PLACEHOLDER:
            if self.env == "dev":
                # En desarrollo se usa una clave predecible para simplificar pruebas
                # y evitar fallos al ejecutar la suite sin variables de entorno.
                self.secret_key = "dev-secret-key"
            else:
                raise RuntimeError(
                    "SECRET_KEY debe sobrescribirse; reemplace el placeholder 'REEMPLAZAR_SECRET_KEY'"
                )
        if self.admin_pass == ADMIN_PASS_PLACEHOLDER:
            if self.env == "dev":
                # Contraseña por defecto solo válida para entornos de desarrollo.
                # En producción el arranque abortará si no se define un valor seguro.
                self.admin_pass = "dev-admin-pass"
            else:
                raise RuntimeError(
                    "ADMIN_PASS debe sobrescribirse; reemplace el placeholder 'REEMPLAZAR_ADMIN_PASS'"
                )

        raw = os.getenv("ALLOWED_ORIGINS", "").split(",")
        origins = [o.strip() for o in raw if o.strip()]
        if self.env == "dev":
            if not origins:
                origins = ["http://localhost:5173"]
            origins = _expand_local(origins)
        elif not origins:
            raise RuntimeError(
                "En producción, ALLOWED_ORIGINS debe definir al menos un origen"
            )
        self.allowed_origins = origins


settings = Settings()
