#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: settings.py
# NG-HEADER: Ubicación: services/meli/settings.py
# NG-HEADER: Descripción: Configuración validada y fail-fast del runtime Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Configuración sin valores sensibles serializables ni defaults inseguros."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_core.secrets import SecretConfigurationError, read_secret


class MeliConfigurationError(RuntimeError):
    """La integración no puede arrancar de forma segura."""


class MeliSettings(BaseSettings):
    """Valores operativos no secretos leídos desde el entorno."""

    model_config = SettingsConfigDict(env_prefix="MELI_", extra="ignore")

    redirect_uri: str = ""
    api_base_url: str = "https://api.mercadolibre.com"
    authorization_url: str = "https://auth.mercadolibre.com.ar/authorization"
    allowed_topics: str = "items,orders_v2,questions,messages"
    request_timeout_seconds: float = 10.0
    webhook_max_bytes: int = 65_536
    oauth_state_ttl_seconds: int = 600


@dataclass(frozen=True)
class MeliRuntimeConfig:
    app_id: SecretStr
    client_secret: SecretStr
    token_encryption_key: SecretStr
    redirect_uri: str
    api_base_url: str
    authorization_url: str
    allowed_topics: frozenset[str]
    request_timeout_seconds: float
    webhook_max_bytes: int
    oauth_state_ttl_seconds: int


def _required_secret(name: str) -> SecretStr:
    try:
        value = read_secret(name, required=True)
    except SecretConfigurationError as exc:
        raise MeliConfigurationError(str(exc)) from exc
    assert value is not None
    return SecretStr(value)


def load_meli_runtime_config() -> MeliRuntimeConfig:
    """Carga credenciales y valida invariantes antes de aceptar tráfico."""
    settings = MeliSettings()
    app_id = _required_secret("MELI_APP_ID")
    client_secret = _required_secret("MELI_CLIENT_SECRET")
    encryption_key = _required_secret("MELI_TOKEN_ENCRYPTION_KEY")
    if not settings.redirect_uri.startswith("https://"):
        raise MeliConfigurationError("meli_redirect_uri_https_required")
    if settings.oauth_state_ttl_seconds < 60 or settings.oauth_state_ttl_seconds > 900:
        raise MeliConfigurationError("meli_oauth_state_ttl_invalid")
    if settings.webhook_max_bytes < 1024 or settings.webhook_max_bytes > 1_048_576:
        raise MeliConfigurationError("meli_webhook_max_bytes_invalid")
    topics = frozenset(value.strip() for value in settings.allowed_topics.split(",") if value.strip())
    if not topics:
        raise MeliConfigurationError("meli_allowed_topics_missing")
    return MeliRuntimeConfig(
        app_id=app_id,
        client_secret=client_secret,
        token_encryption_key=encryption_key,
        redirect_uri=settings.redirect_uri,
        api_base_url=settings.api_base_url.rstrip("/"),
        authorization_url=settings.authorization_url,
        allowed_topics=topics,
        request_timeout_seconds=settings.request_timeout_seconds,
        webhook_max_bytes=settings.webhook_max_bytes,
        oauth_state_ttl_seconds=settings.oauth_state_ttl_seconds,
    )
