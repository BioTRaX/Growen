# NG-HEADER: Nombre de archivo: openai_provider.py
# NG-HEADER: Ubicación: ai/providers/openai_provider.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Proveedor remoto OpenAI."""
from __future__ import annotations

from typing import Iterable

from ..provider_base import ILLMProvider
from ..types import Task


class OpenAIProvider(ILLMProvider):
    name = "openai"

    def supports(self, task: str) -> bool:
        return task in {Task.CONTENT.value, Task.SEO.value, Task.REASONING.value}

    def generate(self, prompt: str) -> Iterable[str]:
        yield f"openai:{prompt}"
