# NG-HEADER: Nombre de archivo: rate_limit.py
# NG-HEADER: Ubicación: services/chat/rate_limit.py
# NG-HEADER: Descripción: Rate limit distribuido Redis por sujeto HMAC.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Ventana deslizante atómica; memoria sólo se permite fuera de producción."""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import defaultdict, deque

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  redis.call('PEXPIRE', key, 61000)
  return 0
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, 61000)
return 1
"""


async def _allow_memory(subject_hmac: str, limit_per_minute: int) -> bool:
    now = time.monotonic()
    async with _lock:
        window = _windows[subject_hmac]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= max(1, limit_per_minute):
            return False
        window.append(now)
        return True


async def _allow_redis(subject_hmac: str, limit_per_minute: int) -> bool:
    import redis.asyncio as redis

    prefix = os.getenv("TELEGRAM_RATE_LIMIT_REDIS_PREFIX", "growen:telegram:rate")
    key = f"{prefix}:{subject_hmac}"
    now_ms = int(time.time() * 1000)
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    try:
        result = await client.eval(
            _SLIDING_WINDOW_LUA,
            1,
            key,
            now_ms,
            now_ms - 60_000,
            max(1, limit_per_minute),
            f"{now_ms}:{uuid.uuid4().hex}",
        )
        return int(result) == 1
    finally:
        await client.aclose()


async def allow_subject(subject_hmac: str, limit_per_minute: int) -> bool:
    backend = os.getenv("CHAT_RATE_LIMIT_BACKEND", "memory").lower()
    production = os.getenv("ENV", "dev") not in {"dev", "test", "testing"}
    if backend == "memory":
        if production:
            return False
        return await _allow_memory(subject_hmac, limit_per_minute)
    if backend != "redis":
        return False
    try:
        return await _allow_redis(subject_hmac, limit_per_minute)
    except Exception:
        # Redis configurado implica fail-closed también en desarrollo para que
        # una caída no amplíe accidentalmente el límite.
        return False
