# NG-HEADER: Nombre de archivo: router.py
# NG-HEADER: Ubicación: services/intents/router.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Enrutador de intents y dispatcher de handlers."""

from __future__ import annotations

import shlex
from typing import Any, Callable, Dict, List, Tuple

from agent_core import nlu

from . import handlers

# Mapa de intents a funciones handler.
HANDLERS: dict[str, Callable[[List[str], Dict[str, Any]], dict[str, Any]]] = {
    "help": handlers.handle_help,
    "stock": handlers.handle_stock,
    "import": handlers.handle_import,
    "search": handlers.handle_search,
}


def parse_options(text: str) -> Tuple[List[str], Dict[str, Any]]:
    """Divide ``text`` en posicionales y opciones estilo ``argparse``."""
    args: List[str] = []
    opts: Dict[str, Any] = {}
    for token in shlex.split(text):
        if token.startswith("--"):
            key = token[2:]
            if "=" in key:
                key, value = key.split("=", 1)
                opts[key.replace("-", "_")] = value
            else:
                opts[key.replace("-", "_")] = True
        else:
            args.append(token)
    return args, opts


def route(message: str) -> Tuple[str, List[str], Dict[str, Any]]:
    """Devuelve el intent y los argumentos detectados en el mensaje."""
    parsed = nlu.parse(message)
    if parsed:
        args, opts = parse_options(parsed.args)
        return parsed.command, args, opts
    return "unknown", [], {}


def handle(message: str) -> dict[str, Any]:
    """Procesa el mensaje ejecutando el handler asociado al intent.

    Levanta ``KeyError`` si el intent no está registrado.
    """

    intent, args, opts = route(message)
    handler = HANDLERS.get(intent)
    if handler:
        return handler(args, opts)
    raise KeyError(intent)
