# NG-HEADER: Nombre de archivo: memory.py
# NG-HEADER: Ubicacion: services/chat/memory.py
# NG-HEADER: Descripcion: Memoria corta para el chatbot de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Estado efimero para recordar consultas recientes del chatbot."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional

from services.chat.price_lookup import ProductQuery

@dataclass
class MemoryState:
    query: ProductQuery
    pending_clarification: bool
    prompted: bool
    intent: str
    last_render: str
    created_at: float

    def touch(self) -> None:
        self.created_at = time.time()


_TTL_SECONDS = 300
_MEMORY: Dict[str, MemoryState] = {}


def _prune(now: Optional[float] = None) -> None:
    if not _MEMORY:
        return
    if now is None:
        now = time.time()
    expired = [key for key, state in _MEMORY.items() if now - state.created_at > _TTL_SECONDS]
    for key in expired:
        _MEMORY.pop(key, None)


def get_memory(key: str) -> Optional[MemoryState]:
    now = time.time()
    _prune(now)
    state = _MEMORY.get(key)
    if state:
        state.touch()
    return state


def set_memory(key: str, state: MemoryState) -> None:
    _MEMORY[key] = state


def clear_memory(key: str) -> None:
    _MEMORY.pop(key, None)


def ensure_memory(key: str, query: ProductQuery, *, pending: bool, rendered: str) -> MemoryState:
    state = MemoryState(
        query=query,
        pending_clarification=pending,
        prompted=False,
        intent=query.intent,
        last_render=rendered,
        created_at=time.time(),
    )
    set_memory(key, state)
    return state


def mark_prompted(key: str) -> None:
    state = _MEMORY.get(key)
    if state:
        state.prompted = True
        state.touch()


def mark_resolved(key: str) -> None:
    state = _MEMORY.get(key)
    if state:
        state.pending_clarification = False
        state.prompted = False
        state.touch()

def build_memory_key(*, session_id: Optional[str], role: str, host: Optional[str], user_agent: Optional[str] = None) -> str:
    if session_id:
        return f"sess:{session_id}"
    base = host or "unknown"
    if user_agent:
        suffix = format(abs(hash(user_agent)) & 0xFFFF, "04x")
        base = f"{base}:{suffix}"
    return f"anon:{role}:{base}"
