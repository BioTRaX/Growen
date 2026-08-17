#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_telegram_backpressure.py
# NG-HEADER: Ubicación: tests/test_telegram_backpressure.py
# NG-HEADER: Descripción: Prueba de cola acotada y liberación de locks Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import asyncio
import base64

import pytest

from workers import telegram_polling


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_queue_size_two_applies_backpressure_and_releases_subject_lock(monkeypatch):
    monkeypatch.delenv("TELEGRAM_IDENTITY_HMAC_KEY_FILE", raising=False)
    monkeypatch.setenv("TELEGRAM_IDENTITY_HMAC_KEY", base64.urlsafe_b64encode(b"h" * 32).decode())
    release = asyncio.Event()
    started = asyncio.Event()

    async def slow_process(update, bot_hash):
        started.set()
        await release.wait()

    monkeypatch.setattr(telegram_polling, "_process_update", slow_process)
    queue = asyncio.Queue(maxsize=2)
    locks = {}
    worker = asyncio.create_task(telegram_polling._queue_worker(queue, "b" * 64, locks))
    await queue.put({"update_id": 1, "message": {"from": {"id": 7}}})
    await started.wait()
    await queue.put({"update_id": 2, "message": {"from": {"id": 7}}})
    await queue.put({"update_id": 3, "message": {"from": {"id": 7}}})
    blocked_put = asyncio.create_task(queue.put({"update_id": 4, "message": {"from": {"id": 7}}}))
    await asyncio.sleep(0)
    assert blocked_put.done() is False
    release.set()
    await blocked_put
    await queue.join()
    await queue.put(None)
    await worker
    assert locks == {}
