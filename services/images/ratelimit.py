from __future__ import annotations

import asyncio
import os
import time
from typing import Optional


class _TokenBucket:
    def __init__(self, rate_rps: float, burst: int) -> None:
        self.rate = max(0.1, float(rate_rps))
        self.capacity = max(1, int(burst))
        self.tokens = float(self.capacity)
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        delta = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + delta * self.rate)

    async def acquire(self) -> None:
        # Async acquire for async callers
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # compute wait time for one token
                missing = 1.0 - self.tokens
                wait_s = missing / self.rate
            await asyncio.sleep(max(0.0, wait_s))

    def acquire_sync(self) -> None:
        # Sync acquire for sync callers (uses time.sleep)
        import time as _t

        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            missing = 1.0 - self.tokens
            wait_s = missing / self.rate
            _t.sleep(max(0.0, wait_s))


_singleton: Optional[_TokenBucket] = None


def get_limiter() -> _TokenBucket:
    global _singleton
    if _singleton is None:
        rate = float(os.getenv("CRAWL_RATE_REQS_PER_SEC", "1"))
        burst = int(os.getenv("CRAWL_BURST", "3"))
        _singleton = _TokenBucket(rate, burst)
    return _singleton

