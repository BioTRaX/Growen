#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: crypto.py
# NG-HEADER: Ubicación: services/meli/crypto.py
# NG-HEADER: Descripción: Cifrado autenticado de tokens y verificadores OAuth de Mercado Libre.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""AES-256-GCM con AAD por propósito y cuenta."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from services.meli.settings import MeliConfigurationError, load_meli_runtime_config


class MeliCryptoError(RuntimeError):
    """El material criptográfico o ciphertext no es válido."""


def _decode_key(value: str) -> bytes:
    try:
        raw = bytes.fromhex(value) if len(value) == 64 else base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise MeliCryptoError("meli_encryption_key_invalid") from exc
    if len(raw) != 32:
        raise MeliCryptoError("meli_encryption_key_invalid_length")
    return raw


class TokenCipher:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise MeliCryptoError("meli_encryption_key_invalid_length")
        self._cipher = AESGCM(key)

    @classmethod
    def from_runtime(cls) -> "TokenCipher":
        try:
            value = load_meli_runtime_config().token_encryption_key.get_secret_value()
        except MeliConfigurationError:
            # Permite tests criptográficos focales sin obligar credenciales OAuth no usadas.
            from agent_core.secrets import read_secret

            value = read_secret("MELI_TOKEN_ENCRYPTION_KEY", required=True)
        assert value is not None
        return cls(_decode_key(value))

    @staticmethod
    def _aad(purpose: str, account_ref: str) -> bytes:
        return f"growen:meli:{purpose}:{account_ref}".encode("utf-8")

    def encrypt(self, plaintext: str, *, purpose: str, account_ref: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), self._aad(purpose, account_ref))
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, encoded: str, *, purpose: str, account_ref: str) -> str:
        try:
            packed = base64.urlsafe_b64decode(encoded.encode("ascii"))
            return self._cipher.decrypt(packed[:12], packed[12:], self._aad(purpose, account_ref)).decode("utf-8")
        except Exception as exc:
            raise MeliCryptoError("meli_ciphertext_invalid") from exc
