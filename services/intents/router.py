"""Enrutador de intents y dispatcher de handlers."""

from __future__ import annotations

from typing import Any, Callable

from agent_core import nlu

from . import handlers

# Mapa de intents a funciones handler.
HANDLERS: dict[str, Callable[[], dict[str, Any]]] = {
    "help": handlers.handle_help,
}


def route(message: str) -> str:
    """Devuelve el intent detectado a partir del mensaje."""
    parsed = nlu.parse(message)
    if parsed:
        return parsed.command
    return "unknown"


def handle(message: str) -> dict[str, Any]:
    """Procesa el mensaje ejecutando el handler asociado al intent.

    Levanta ``KeyError`` si el intent no está registrado.
    """

    intent = route(message)
    handler = HANDLERS.get(intent)
    if handler:
        return handler()
    raise KeyError(intent)
