# NG-HEADER: Nombre de archivo: scheduler.py
# NG-HEADER: Ubicación: agent_core/scheduler.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Planificador mínimo basado en funciones asíncronas."""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Awaitable, Callable


class Scheduler:
    """Cola de tareas asíncronas ejecutadas secuencialmente."""

    def __init__(self) -> None:
        self._queue: deque[Callable[[], Awaitable[None]]] = deque()

    def add(self, coro_factory: Callable[[], Awaitable[None]]) -> None:
        self._queue.append(coro_factory)

    async def run(self) -> None:
        while self._queue:
            await self._queue.popleft()()
