"""Configuración central del agente."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Parámetros de configuración leídos de variables de entorno."""

    env: str = os.getenv("ENV", "dev")
    db_url: str = os.getenv(
        "DB_URL", "postgresql+psycopg://growen:growen@localhost:5432/growen"
    )
    ai_mode: str = os.getenv("AI_MODE", "auto")
    ai_allow_external: bool = os.getenv("AI_ALLOW_EXTERNAL", "true").lower() == "true"


settings = Settings()
