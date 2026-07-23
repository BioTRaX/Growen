#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: rate_limit.py
# NG-HEADER: Ubicación: services/chat/rate_limit.py
# NG-HEADER: Descripción: Rate limit acotado por sujeto para canales públicos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Ventana deslizante en memoria sin almacenar identificadores externos."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


async def allow_subject(subject_hmac: str, limit_per_minute: int) -> bool:
    now = time.monotonic()
    async with _lock:
        window = _windows[subject_hmac]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= max(1, limit_per_minute):
            return False
        window.append(now)
        return True
