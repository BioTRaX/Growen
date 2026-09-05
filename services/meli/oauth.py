#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: oauth.py
# NG-HEADER: Ubicación: services/meli/oauth.py
# NG-HEADER: Descripción: Flujo OAuth Authorization Code con PKCE y state de un uso para MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""OAuth server-side con persistencia cifrada y protección contra replay."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MeliAccount, MeliOAuthState
from services.meli.crypto import TokenCipher
from services.meli.settings import MeliRuntimeConfig


class MeliOAuthError(RuntimeError):
    """El flujo OAuth fue inválido, expiró o intentó repetirse."""


@dataclass(frozen=True)
class AuthorizationRequest:
    authorization_url: str
    state: str
    code_verifier: str
    expires_at: datetime


def _state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def create_authorization(
    db: AsyncSession,
    *,
    requested_by_user_id: int | None,
    config: MeliRuntimeConfig,
    cipher: TokenCipher,
) -> AuthorizationRequest:
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    digest = _state_hash(state)
    expires_at = datetime.utcnow() + timedelta(seconds=config.oauth_state_ttl_seconds)
    db.add(
        MeliOAuthState(
            state_hash=digest,
            code_verifier_ciphertext=cipher.encrypt(verifier, purpose="pkce", account_ref=digest),
            redirect_uri=config.redirect_uri,
            requested_by_user_id=requested_by_user_id,
            expires_at=expires_at,
        )
    )
    await db.commit()
    query = urlencode(
        {
            "response_type": "code",
            "scope": "read write offline_access",
            "client_id": config.app_id.get_secret_value(),
            "redirect_uri": config.redirect_uri,
            "state": state,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return AuthorizationRequest(f"{config.authorization_url}?{query}", state, verifier, expires_at)


async def complete_authorization(
    db: AsyncSession,
    *,
    state: str,
    code: str,
    config: MeliRuntimeConfig,
    cipher: TokenCipher,
    client,
) -> MeliAccount:
    digest = _state_hash(state)
    oauth_state = await db.scalar(
        select(MeliOAuthState).where(MeliOAuthState.state_hash == digest).with_for_update()
    )
    if oauth_state is None:
        raise MeliOAuthError("meli_oauth_state_invalid")
    if oauth_state.consumed_at is not None:
        raise MeliOAuthError("meli_oauth_state_already_used")
    if oauth_state.expires_at <= datetime.utcnow():
        raise MeliOAuthError("meli_oauth_state_expired")
    verifier = cipher.decrypt(oauth_state.code_verifier_ciphertext, purpose="pkce", account_ref=digest)
    token = await client.exchange_code(code=code, redirect_uri=oauth_state.redirect_uri, code_verifier=verifier)
    access = str(token["access_token"])
    refresh = str(token["refresh_token"])
    me = await client.get_me(access)
    seller_id = int(me["id"])
    token_user_id = int(token.get("user_id", seller_id))
    if token_user_id != seller_id:
        raise MeliOAuthError("meli_oauth_seller_mismatch")
    app_id = config.app_id.get_secret_value()
    account = await db.scalar(
        select(MeliAccount)
        .where(MeliAccount.application_id == app_id, MeliAccount.seller_id == seller_id)
        .with_for_update()
    )
    if account is None:
        account = MeliAccount(
            application_id=app_id,
            seller_id=seller_id,
            access_token_ciphertext="pending",
            refresh_token_ciphertext="pending",
            token_expires_at=datetime.utcnow(),
        )
        db.add(account)
    account.site_id = me.get("site_id")
    account.scopes = token.get("scope")
    account.access_token_ciphertext = cipher.encrypt(access, purpose="access", account_ref=str(seller_id))
    account.refresh_token_ciphertext = cipher.encrypt(refresh, purpose="refresh", account_ref=str(seller_id))
    account.token_expires_at = datetime.utcnow() + timedelta(seconds=int(token["expires_in"]))
    account.token_version = (account.token_version or 0) + 1
    account.status = "active"
    account.last_error_code = None
    oauth_state.consumed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)
    return account
