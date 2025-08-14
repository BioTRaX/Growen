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
