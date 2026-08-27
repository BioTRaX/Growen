#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: settings.py
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/settings.py
# NG-HEADER: Descripción: Configuración y lectura segura de secretos del MCP de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from .client import SiYuanConfigurationError


load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SECRET_DIR = _REPO_ROOT.parent / "growen-secrets"


def load_api_token() -> str:
    token_file = os.getenv(
        "SIYUAN_API_TOKEN_FILE", str(_DEFAULT_SECRET_DIR / "siyuan_api_token")
    ).strip()
    if token_file:
        path = Path(token_file).expanduser()
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SiYuanConfigurationError("siyuan_token_file_unreadable") from exc
        if value:
            return value
    value = os.getenv("SIYUAN_API_TOKEN", "").strip()
    if not value:
        raise SiYuanConfigurationError("siyuan_token_missing")
    return value


def load_mcp_secret() -> str:
    secret_file = os.getenv(
        "MCP_SIYUAN_SECRET_KEY_FILE", str(_DEFAULT_SECRET_DIR / "mcp_siyuan_secret_key")
    ).strip()
    if secret_file:
        try:
            value = Path(secret_file).expanduser().read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SiYuanConfigurationError("mcp_siyuan_secret_file_unreadable") from exc
        if value:
            return value
    value = os.getenv("MCP_SIYUAN_SECRET_KEY", "").strip()
    if not value:
        raise SiYuanConfigurationError("mcp_siyuan_secret_missing")
    return value


@dataclass(frozen=True)
class SiYuanSettings:
    base_url: str
    notebook_name: str
    notebook_id: str | None
    allowed_path_prefix: str
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "SiYuanSettings":
        return cls(
            base_url=os.getenv("SIYUAN_BASE_URL", "http://localhost:6806").rstrip("/"),
            notebook_name=os.getenv("SIYUAN_NOTEBOOK_NAME", "Nice Grow").strip(),
            notebook_id=os.getenv("SIYUAN_NOTEBOOK_ID", "").strip() or None,
            allowed_path_prefix=os.getenv("SIYUAN_ALLOWED_PATH_PREFIX", "/Growen").rstrip("/"),
            timeout_seconds=float(os.getenv("SIYUAN_TIMEOUT_SECONDS", "10")),
        )


__all__ = ["SiYuanSettings", "load_api_token", "load_mcp_secret"]
