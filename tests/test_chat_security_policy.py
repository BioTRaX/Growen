#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_security_policy.py
# NG-HEADER: Ubicación: tests/test_chat_security_policy.py
# NG-HEADER: Descripción: Pruebas de roles, sanitización, cifrado y scopes del chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import base64
from datetime import datetime, timedelta

import pytest

from agent_core.chat_policy import effective_role, normalize_role, public_product_result, tool_allowed
from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task
from db.models import KnowledgeSource, User
from services.chat.external_identity import (
    consume_link_code,
    create_link_request,
    decrypt_external_id,
    encrypt_external_id,
    resolve_identity,
    revoke_identity,
    subject_hmac,
)
from services.chat.orchestrator import ChatRequestContext
from services.rag.search import RAGSearchService


def test_anon_is_normalized_and_unknown_tools_are_denied() -> None:
    assert normalize_role("anon") == "guest"
    assert tool_allowed("get_product_info", "guest", "telegram") is True
    assert tool_allowed("unknown_tool", "admin", "web") is False


def test_telegram_applies_admin_ceiling(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHANNEL_ROLE_CEILING", "colaborador")
    assert effective_role("admin", "telegram") == "colaborador"
    assert effective_role("admin", "web") == "admin"
    context = ChatRequestContext.build(channel="telegram", conversation_id="opaque", account_role="admin")
    assert context.account_role == "admin"
    assert context.effective_role == "colaborador"


def test_external_ai_fails_closed_without_local_provider(monkeypatch) -> None:
    monkeypatch.setenv("AI_DISABLE_OLLAMA", "true")
    monkeypatch.setattr(settings, "ai_allow_external", False)
    router = AIRouter(settings)
    with pytest.raises(RuntimeError, match="ai_external_disabled"):
        router.get_provider(Task.SHORT_ANSWER.value)


def test_public_product_result_recursively_hides_exact_inventory() -> None:
    result = public_product_result(
        {"items": [{"name": "A", "sku": "SECRET", "supplier_sku": "OTHER", "supplier_name": "Privado", "source_detail": "interno", "stock_qty": 3, "sale_price": 10, "nested": {"unique_sku": "NESTED"}}]},
        "cliente",
    )
    assert result["items"][0]["availability"] == "disponible"
    assert "sku" not in result["items"][0]
    assert "stock" not in result["items"][0]
    assert "stock_qty" not in result["items"][0]
    assert "supplier_sku" not in result["items"][0]
    assert "supplier_name" not in result["items"][0]
    assert "source_detail" not in result["items"][0]
    assert "unique_sku" not in result["items"][0]["nested"]


def test_external_id_uses_separate_encryption_and_hmac_keys(monkeypatch) -> None:
    encryption = base64.urlsafe_b64encode(b"e" * 32).decode("ascii")
    hmac_key = base64.urlsafe_b64encode(b"h" * 32).decode("ascii")
    monkeypatch.delenv("TELEGRAM_IDENTITY_ENCRYPTION_KEY_FILE", raising=False)
    monkeypatch.delenv("TELEGRAM_IDENTITY_HMAC_KEY_FILE", raising=False)
    monkeypatch.setenv("TELEGRAM_IDENTITY_ENCRYPTION_KEY", encryption)
    monkeypatch.setenv("TELEGRAM_IDENTITY_HMAC_KEY", hmac_key)
    ciphertext = encrypt_external_id("telegram", 123456)
    assert "123456" not in ciphertext
    assert decrypt_external_id("telegram", ciphertext) == "123456"
    assert subject_hmac("telegram", 123456) == subject_hmac("telegram", "123456")


@pytest.mark.asyncio
async def test_admin_link_is_pending_revocable_and_role_is_read_live(db_session, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_IDENTITY_ENCRYPTION_KEY_FILE", raising=False)
    monkeypatch.delenv("TELEGRAM_IDENTITY_HMAC_KEY_FILE", raising=False)
    monkeypatch.setenv("TELEGRAM_IDENTITY_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"e" * 32).decode("ascii"))
    monkeypatch.setenv("TELEGRAM_IDENTITY_HMAC_KEY", base64.urlsafe_b64encode(b"h" * 32).decode("ascii"))
    monkeypatch.setattr(settings, "telegram_role_linking_enabled", True)
    monkeypatch.setattr(settings, "telegram_admin_second_approval", True)
    user = User(identifier="admin-link", password_hash="unused", role="admin")
    db_session.add(user)
    await db_session.commit()

    code, _ = await create_link_request(db_session, user)
    identity, account_role = await consume_link_code(db_session, code=code, telegram_user_id=987654)
    assert account_role == "admin"
    assert identity.status == "pending_approval"
    assert (await resolve_identity(db_session, provider="telegram", external_id=987654, channel="telegram")).account_role == "guest"

    identity.status = "active"
    await db_session.commit()
    resolved = await resolve_identity(db_session, provider="telegram", external_id=987654, channel="telegram")
    assert resolved.account_role == "admin"
    assert resolved.effective_role == "colaborador"

    user.role = "cliente"
    await db_session.commit()
    resolved = await resolve_identity(db_session, provider="telegram", external_id=987654, channel="telegram")
    assert resolved.account_role == "cliente"
    await revoke_identity(db_session, identity, user.id)
    assert (await resolve_identity(db_session, provider="telegram", external_id=987654, channel="telegram")).account_role == "guest"


def test_rag_source_scope_is_deny_by_default() -> None:
    service = object.__new__(RAGSearchService)
    source = KnowledgeSource(
        filename="seguro.md",
        hash="0" * 64,
        role_scope=["colaborador"],
        channel_scope=["web"],
        status="active",
        visibility="internal",
        content_version=1,
    )
    assert service._source_allowed(source, "colaborador", "web") is True
    assert service._source_allowed(source, "guest", "web") is False
    source.status = "stale"
    assert service._source_allowed(source, "colaborador", "web") is False
    source.status = "active"
    source.expires_at = datetime.utcnow() - timedelta(seconds=1)
    assert service._source_allowed(source, "colaborador", "web") is False
