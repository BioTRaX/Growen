"""Proveedor local Ollama."""
from __future__ import annotations

from typing import Iterable

from ..provider_base import ILLMProvider
from ..types import Task


class OllamaProvider(ILLMProvider):
    name = "ollama"

    def supports(self, task: str) -> bool:
        return task in {Task.NLU_PARSE.value, Task.NLU_INTENT.value, Task.SHORT_ANSWER.value}

    def generate(self, prompt: str) -> Iterable[str]:
        yield f"ollama:{prompt}"
