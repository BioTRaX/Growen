"""Política de decisión para elegir proveedor de IA."""

from __future__ import annotations

import os
from typing import Literal

Task = Literal[
    "nlu.parse_command",
    "nlu.intent",
    "short_answer",
    "content.generation",
    "seo.product_desc",
    "reasoning.heavy",
]


_DEFAULTS: dict[Task, str] = {
    "nlu.parse_command": "ollama",
    "nlu.intent": "ollama",
    "short_answer": "ollama",
    "content.generation": "openai",
    "seo.product_desc": "openai",
    "reasoning.heavy": "openai",
}


def choose_provider(task: Task, context: dict | None = None) -> Literal["ollama", "openai"]:
    """Devuelve el nombre del proveedor a usar."""

    context = context or {}
    override = context.get("override")
    if override in {"openai", "ollama"}:
        return override  # preferencia explícita

    mode = os.getenv("AI_MODE", "auto")
    if mode in {"openai", "ollama"}:
        return mode  # modo forzado global

    env = os.getenv("ENV", "dev")
    if env == "dev_offline":
        return "ollama"

    if not os.getenv("OPENAI_API_KEY"):
        return "ollama"

    if not (os.getenv("OLLAMA_HOST") and os.getenv("OLLAMA_MODEL")):
        return "openai"

    return _DEFAULTS[task]
