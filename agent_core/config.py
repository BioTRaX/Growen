# NG-HEADER: Nombre de archivo: config.py
# NG-HEADER: Ubicación: agent_core/config.py
# NG-HEADER: Descripción: Constantes y configuración central del agente.
# NG-HEADER: Lineamientos: Ver AGENTS.md
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
    # Soporte para componer la URL si no se pasa DB_URL directamente
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: str = os.getenv("DB_PORT", "5432")
    db_name: str = os.getenv("DB_NAME", "growen")
    db_user: str = os.getenv("DB_USER", "growen")
    db_pass: str = os.getenv("DB_PASS", "")
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
    # Modo desarrollo: permite asumir rol admin sin sesión (solo dev, nunca prod)
    dev_assume_admin: bool = os.getenv("DEV_ASSUME_ADMIN", "false").lower() == "true"
    # Token secreto para autenticación entre servicios internos (MCP servers, workers)
    internal_service_token: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")

    # Configuracion de importacion de PDFs
    import_ocr_lang: str = os.getenv("IMPORT_OCR_LANG", "spa+eng")
    import_ocr_timeout: int = int(os.getenv("IMPORT_OCR_TIMEOUT", "180"))
    import_pdf_text_min_chars: int = int(os.getenv("IMPORT_PDF_TEXT_MIN_CHARS", "200"))
    import_allow_empty_draft: bool = os.getenv("IMPORT_ALLOW_EMPTY_DRAFT", "true").lower() == "true"

    # Configuración IA fallback import remitos
    import_ai_enabled: bool = os.getenv("IMPORT_AI_ENABLED", "false").lower() == "true"
    import_ai_min_confidence: float = float(os.getenv("IMPORT_AI_MIN_CONFIDENCE", "0.86"))
    import_ai_model: str = os.getenv("IMPORT_AI_MODEL", "gpt-4o-mini")
    import_ai_timeout: int = int(os.getenv("IMPORT_AI_TIMEOUT", "40"))  # segundos
    import_ai_max_retries: int = int(os.getenv("IMPORT_AI_MAX_RETRIES", "2"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    import_ai_classic_min_confidence: float = float(os.getenv("IMPORT_AI_CLASSIC_MIN_CONFIDENCE", "0.55"))

    def __post_init__(self) -> None:
        if not self.db_url:
            # Intentar construir desde variables sueltas
            if self.db_pass:
                from urllib.parse import quote_plus as _qp
                pw_enc = _qp(self.db_pass)
            else:
                pw_enc = ""
            if self.db_user and pw_enc:
                candidate = f"postgresql+psycopg://{self.db_user}:{pw_enc}@{self.db_host}:{self.db_port}/{self.db_name}"
            elif self.db_user:
                candidate = f"postgresql+psycopg://{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"
            else:
                candidate = ""
            if candidate:
                self.db_url = candidate
        if not self.db_url:
            if self.env == "dev":
                # Fallback amigable para no bloquear el arranque local sin Postgres
                # Nota: aiosqlite sólo se usa si se instala aiosqlite (ya en requirements)
                self.db_url = "sqlite+aiosqlite:///./dev.db"
            else:
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
                # Fallback de desarrollo (NO usar en producción). Coherente con seed/migración.
                self.admin_pass = "admin1234"
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

        # Fail-safe: forzar dev_assume_admin=False fuera de entorno dev
        if self.env != "dev" and self.dev_assume_admin:
            import logging
            logging.getLogger("growen.config").warning(
                "SEGURIDAD: dev_assume_admin fue ignorado porque ENV=%s (no es 'dev')",
                self.env
            )
            self.dev_assume_admin = False


settings = Settings()
