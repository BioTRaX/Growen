#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_runtime_security.py
# NG-HEADER: Ubicación: tests/test_chat_runtime_security.py
# NG-HEADER: Descripción: Pruebas de secretos, rate limit y recuperación Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from datetime import datetime, timedelta

import pytest

from agent_core.secrets import SecretConfigurationError, read_secret
from db.models import TelegramUpdate
from db.session import SessionLocal
from services.chat.rate_limit import allow_subject
from workers import telegram_polling


@pytest.mark.no_db
def test_secret_file_is_absolute_regular_and_exclusive(monkeypatch, tmp_path):
    secret = tmp_path / "token"
    secret.write_text("valor-seguro\n", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_FILE", str(secret.resolve()))
    assert read_secret("TELEGRAM_BOT_TOKEN", required=True) == "valor-seguro"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "duplicado")
    with pytest.raises(SecretConfigurationError, match="conflict"):
        read_secret("TELEGRAM_BOT_TOKEN")


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_rate_limit_redis_fails_closed(monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT_BACKEND", "redis")

    async def unavailable(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr("services.chat.rate_limit._allow_redis", unavailable)
    assert await allow_subject("a" * 64, 10) is False


@pytest.mark.asyncio
async def test_processing_update_is_recovered_only_after_timeout(monkeypatch):
    monkeypatch.setattr(telegram_polling, "PROCESSING_TIMEOUT", 120)
    async with SessionLocal() as db:
        record = TelegramUpdate(bot_id_hash="b" * 64, update_id=10, status="processing", attempts=1, processing_at=datetime.utcnow())
        db.add(record)
        await db.commit()
    assert await telegram_polling._claim_update("b" * 64, 10) is False
    async with SessionLocal() as db:
        record = await db.get(TelegramUpdate, 1)
        record.processing_at = datetime.utcnow() - timedelta(seconds=121)
        await db.commit()
    assert await telegram_polling._claim_update("b" * 64, 10) is True


@pytest.mark.asyncio
async def test_offset_stops_before_non_terminal_gap():
    async with SessionLocal() as db:
        db.add_all([
            TelegramUpdate(bot_id_hash="c" * 64, update_id=20, status="succeeded", attempts=1),
            TelegramUpdate(bot_id_hash="c" * 64, update_id=21, status="queued", attempts=1),
            TelegramUpdate(bot_id_hash="c" * 64, update_id=22, status="succeeded", attempts=1),
        ])
        await db.commit()
    assert await telegram_polling._contiguous_terminal_offset("c" * 64, [20, 21, 22], 19) == 20
