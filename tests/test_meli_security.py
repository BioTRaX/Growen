#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_meli_security.py
# NG-HEADER: Ubicación: tests/test_meli_security.py
# NG-HEADER: Descripción: Pruebas de configuración, cifrado y metadatos seguros de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import base64

import pytest


def test_runtime_config_fails_when_required_credentials_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detecta la regresión donde el servicio arranca sin credenciales obligatorias."""
    from services.meli.settings import MeliConfigurationError, load_meli_runtime_config

    for name in (
        "MELI_APP_ID",
        "MELI_APP_ID_FILE",
        "MELI_CLIENT_SECRET",
        "MELI_CLIENT_SECRET_FILE",
        "MELI_TOKEN_ENCRYPTION_KEY",
        "MELI_TOKEN_ENCRYPTION_KEY_FILE",
        "MELI_REDIRECT_URI",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(MeliConfigurationError, match="meli_app_id_missing"):
        load_meli_runtime_config()


def test_token_cipher_requires_correct_domain_aad(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detecta que un token pueda descifrarse fuera de su cuenta y propósito."""
    from services.meli.crypto import MeliCryptoError, TokenCipher

    raw_key = base64.urlsafe_b64encode(b"m" * 32).decode("ascii")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("MELI_TOKEN_ENCRYPTION_KEY_FILE", raising=False)
    monkeypatch.setenv("MELI_TOKEN_ENCRYPTION_KEY", raw_key)
    cipher = TokenCipher.from_runtime()

    encrypted = cipher.encrypt("token-opaco", purpose="access", account_ref="seller-42")

    assert cipher.decrypt(encrypted, purpose="access", account_ref="seller-42") == "token-opaco"
    with pytest.raises(MeliCryptoError, match="meli_ciphertext_invalid"):
        cipher.decrypt(encrypted, purpose="refresh", account_ref="seller-42")


def test_meli_models_expose_durable_tables() -> None:
    """Detecta la pérdida del estado durable necesario para deduplicar y recuperar trabajos."""
    import db.models  # noqa: F401
    from db.base import Base

    expected = {
        "meli_accounts",
        "meli_oauth_states",
        "meli_notifications",
        "meli_item_links",
        "meli_sync_jobs",
    }
    assert expected <= set(Base.metadata.tables)


def test_meli_migration_is_the_single_head() -> None:
    """Detecta que el esquema MeLi quede fuera de la cadena desplegable."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["20260905_meli_scopes_text"]
