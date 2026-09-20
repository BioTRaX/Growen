#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: external_identity.py
# NG-HEADER: Ubicación: services/chat/external_identity.py
# NG-HEADER: Descripción: Identidad externa cifrada, vínculo y revocación.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Identidad externa cifrada con AES-GCM e índice HMAC determinista."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.chat_policy import effective_role, normalize_role
from agent_core.config import settings
from agent_core.secrets import SecretConfigurationError, read_secret
from db.models import ExternalIdentity, ExternalIdentityLinkRequest, User


class IdentityConfigurationError(RuntimeError):
    """La configuración criptográfica no permite operar de forma segura."""


@dataclass(frozen=True)
class ResolvedIdentity:
    identity_id: int | None
    user_id: int | None
    account_role: str
    effective_role: str
    subject_hmac: str


def _decode_key(name: str, *, required: bool = True) -> bytes | None:
    try:
        value = read_secret(name, required=required)
    except SecretConfigurationError as exc:
        raise IdentityConfigurationError(str(exc)) from exc
    if not value:
        if required:
            raise IdentityConfigurationError(f"{name}_missing")
        return None
    try:
        raw = bytes.fromhex(value) if len(value) == 64 else base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise IdentityConfigurationError(f"{name}_invalid") from exc
    if len(raw) != 32:
        raise IdentityConfigurationError(f"{name}_invalid_length")
    return raw


def subject_hmac(provider: str, external_id: int | str) -> str:
    key = _decode_key("TELEGRAM_IDENTITY_HMAC_KEY")
    assert key is not None
    payload = f"{provider}:{external_id}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def encrypt_external_id(provider: str, external_id: int | str) -> str:
    key = _decode_key("TELEGRAM_IDENTITY_ENCRYPTION_KEY")
    assert key is not None
    nonce = os.urandom(12)
    aad = provider.encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, str(external_id).encode("utf-8"), aad)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_external_id(provider: str, ciphertext: str) -> str:
    packed = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    for name in ("TELEGRAM_IDENTITY_ENCRYPTION_KEY", "TELEGRAM_IDENTITY_ENCRYPTION_KEY_PREVIOUS"):
        key = _decode_key(name, required=name.endswith("ENCRYPTION_KEY"))
        if not key:
            continue
        try:
            return AESGCM(key).decrypt(packed[:12], packed[12:], provider.encode("utf-8")).decode("utf-8")
        except Exception:
            continue
    raise IdentityConfigurationError("external_identity_decryption_failed")


def opaque_conversation_key(provider: str, external_id: int | str, chat_id: int | str) -> str:
    key = _decode_key("TELEGRAM_IDENTITY_HMAC_KEY")
    assert key is not None
    payload = f"conversation:{provider}:{external_id}:{chat_id}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def masked_identity(identity: ExternalIdentity) -> str:
    return f"{identity.provider}:••••{identity.external_id_hmac[-6:]}"


async def resolve_identity(
    db: AsyncSession,
    *,
    provider: str,
    external_id: int | str,
    channel: str,
) -> ResolvedIdentity:
    digest = subject_hmac(provider, external_id)
    result = await db.execute(
        select(ExternalIdentity, User)
        .outerjoin(User, User.id == ExternalIdentity.user_id)
        .where(
            ExternalIdentity.provider == provider,
            ExternalIdentity.external_id_hmac == digest,
            ExternalIdentity.status == "active",
        )
    )
    row = result.first()
    if not row or not row.User:
        return ResolvedIdentity(None, None, "guest", "guest", digest)
    identity, user = row[0], row[1]
    identity.last_seen_at = datetime.utcnow()
    role = normalize_role(user.role)
    return ResolvedIdentity(identity.id, user.id, role, effective_role(role, channel), digest)


async def create_link_request(db: AsyncSession, user: User) -> tuple[str, ExternalIdentityLinkRequest]:
    raw_code = secrets.token_urlsafe(12).replace("-", "").replace("_", "").upper()
    token_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    request = ExternalIdentityLinkRequest(
        id=secrets.token_hex(16),
        provider="telegram",
        token_hash=token_hash,
        user_id=user.id,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(seconds=settings.telegram_link_code_ttl_seconds),
    )
    db.add(request)
    await db.commit()
    return raw_code, request


async def consume_link_code(
    db: AsyncSession, *, code: str, telegram_user_id: int | str
) -> tuple[ExternalIdentity, str]:
    if not settings.telegram_role_linking_enabled:
        raise PermissionError("telegram_linking_disabled")
    token_hash = hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()
    result = await db.execute(
        select(ExternalIdentityLinkRequest, User)
        .join(User, User.id == ExternalIdentityLinkRequest.user_id)
        .where(
            ExternalIdentityLinkRequest.token_hash == token_hash,
            ExternalIdentityLinkRequest.status == "pending",
        )
        .with_for_update()
    )
    row = result.first()
    if not row:
        raise ValueError("link_code_invalid")
    request, user = row[0], row[1]
    if request.expires_at <= datetime.utcnow():
        request.status = "expired"
        await db.commit()
        raise ValueError("link_code_expired")

    digest = subject_hmac("telegram", telegram_user_id)
    existing = await db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "telegram",
            ExternalIdentity.external_id_hmac == digest,
        )
    )
    active_for_user = await db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.user_id == user.id,
            ExternalIdentity.provider == "telegram",
            ExternalIdentity.status.in_(("active", "pending_approval")),
        )
    )
    if active_for_user and (not existing or active_for_user.id != existing.id):
        raise ValueError("user_identity_already_linked")
    if existing and existing.user_id not in (None, user.id) and existing.status != "revoked":
        raise ValueError("external_identity_already_linked")

    status = "pending_approval" if user.role == "admin" and settings.telegram_admin_second_approval else "active"
    identity = existing or ExternalIdentity(
        provider="telegram",
        external_id_hmac=digest,
        external_id_ciphertext=encrypt_external_id("telegram", telegram_user_id),
    )
    identity.user_id = user.id
    identity.status = status
    identity.verified_at = datetime.utcnow()
    identity.revoked_at = None
    identity.revoked_by_user_id = None
    if not existing:
        db.add(identity)
        await db.flush()
    request.status = "consumed"
    request.consumed_at = datetime.utcnow()
    request.external_identity_id = identity.id
    await db.commit()
    return identity, normalize_role(user.role)


async def revoke_identity(db: AsyncSession, identity: ExternalIdentity, actor_user_id: int) -> None:
    identity.status = "revoked"
    identity.revoked_by_user_id = actor_user_id
    identity.revoked_at = datetime.utcnow()
    await db.commit()
