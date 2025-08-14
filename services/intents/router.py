"""Enrutador de intents mínimo."""
from __future__ import annotations

from agent_core import nlu


def route(message: str) -> str:
    """Devuelve el intent detectado."""
    parsed = nlu.parse(message)
    if parsed:
        return parsed.command
    return "unknown"
