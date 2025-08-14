"""Fachada para enrutar peticiones de IA."""
from __future__ import annotations

from typing import Iterable

from agent_core.config import Settings
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
        return "".join(provider.generate(prompt))
