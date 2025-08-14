"""Política de selección de proveedores IA."""
from __future__ import annotations

from typing import Dict

from agent_core.config import Settings
from .types import Task

PRIMARY: Dict[str, str] = {
    Task.NLU_PARSE.value: "ollama",
    Task.NLU_INTENT.value: "ollama",
    Task.SHORT_ANSWER.value: "ollama",
    Task.CONTENT.value: "openai",
    Task.SEO.value: "openai",
    Task.REASONING.value: "openai",
}


def choose(task: str, settings: Settings) -> str:
    """Devuelve el proveedor recomendado para la tarea."""
    mode = settings.ai_mode
    if mode == "openai":
        return "openai"
    if mode == "ollama":
        return "ollama"
    return PRIMARY.get(task, "ollama")
