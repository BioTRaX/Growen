"""Configuración central del agente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Marcadores que deben sustituirse en producción
SECRET_KEY_PLACEHOLDER = "REEMPLAZAR_SECRET_KEY"
ADMIN_PASS_PLACEHOLDER = "REEMPLAZAR_ADMIN_PASS"

# Carga automática de variables definidas en .env
load_dotenv()


@dataclass
class Settings:
    """Parámetros de configuración leídos de variables de entorno."""

    env: str = os.getenv("ENV", "dev")
    db_url: str = os.getenv(
        "DB_URL", "postgresql+psycopg://growen:growen@localhost:5432/growen"
    )
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

    def __post_init__(self) -> None:
        if self.secret_key == SECRET_KEY_PLACEHOLDER:
            raise RuntimeError(
                "SECRET_KEY debe sobrescribirse; reemplace el placeholder 'REEMPLAZAR_SECRET_KEY'"
            )
        if self.admin_pass == ADMIN_PASS_PLACEHOLDER:
            raise RuntimeError(
                "ADMIN_PASS debe sobrescribirse; reemplace el placeholder 'REEMPLAZAR_ADMIN_PASS'"
            )


settings = Settings()
