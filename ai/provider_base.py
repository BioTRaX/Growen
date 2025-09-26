# NG-HEADER: Nombre de archivo: provider_base.py
# NG-HEADER: Ubicación: ai/provider_base.py
# NG-HEADER: Descripción: Interfaces base para implementar proveedores de IA.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Interfaz común para proveedores LLM."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class ILLMProvider(ABC):
    name: str

    @abstractmethod
    def supports(self, task: str) -> bool:  # pragma: no cover - interfaz
        """Indica si el proveedor soporta la tarea."""

    @abstractmethod
    def generate(self, prompt: str) -> Iterable[str]:  # pragma: no cover - interfaz
        """Devuelve tokens generados para el prompt."""

    # Streaming opcional: proveedores pueden sobrescribirlo. Por defecto
    # simplemente delega en generate.
    def generate_stream(self, prompt: str) -> Iterable[str]:  # pragma: no cover - fallback simple
        for chunk in self.generate(prompt):
            yield chunk
