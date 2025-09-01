# NG-HEADER: Nombre de archivo: router.py
# NG-HEADER: Ubicación: ai/router.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Fachada para enrutar peticiones de IA."""

from __future__ import annotations

import logging

from agent_core.config import Settings
from .persona import SYSTEM_PROMPT
from .policy import choose
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider


class AIRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers = {
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
        }

    def available_providers(self) -> list[str]:
        providers = ["ollama"]
        if self.settings.ai_allow_external:
            providers.append("openai")
        return providers

    def run(self, task: str, prompt: str) -> str:
        name = choose(task, self.settings)
        if name == "openai" and not self.settings.ai_allow_external:
            name = "ollama"
        provider = self._providers[name]
        if not provider.supports(task):
            logging.warning(
                "Proveedor %s no soporta la tarea %s, usando ollama", name, task
            )
            provider = self._providers["ollama"]
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        return "".join(provider.generate(full_prompt))
