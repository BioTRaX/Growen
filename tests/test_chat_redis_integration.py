#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_chat_redis_integration.py
# NG-HEADER: Ubicación: tests/test_chat_redis_integration.py
# NG-HEADER: Descripción: Integración Redis multiproceso para rate limit de Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import asyncio
import multiprocessing
import os
import uuid

import pytest


def _rate_worker(subject: str, attempts: int, output) -> None:
    from services.chat.rate_limit import allow_subject

    async def run() -> int:
        values = await asyncio.gather(*(allow_subject(subject, 10) for _ in range(attempts)))
        return sum(values)

    output.put(asyncio.run(run()))


@pytest.mark.integration
@pytest.mark.no_db
def test_redis_rate_limit_is_atomic_between_processes(monkeypatch):
    if os.getenv("RUN_REDIS_INTEGRATION") != "1":
        pytest.skip("Definir RUN_REDIS_INTEGRATION=1 con Redis real")
    prefix = f"growen:test:telegram:{uuid.uuid4().hex}"
    monkeypatch.setenv("CHAT_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("TELEGRAM_RATE_LIMIT_REDIS_PREFIX", prefix)
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    processes = [context.Process(target=_rate_worker, args=("d" * 64, 10, output)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    assert sum(output.get(timeout=2) for _ in processes) == 10

    async def cleanup() -> None:
        import redis.asyncio as redis

        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        try:
            await client.delete(f"{prefix}:{'d' * 64}")
        finally:
            await client.aclose()

    asyncio.run(cleanup())
