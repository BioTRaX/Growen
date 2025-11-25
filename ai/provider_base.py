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
        """Devuelve tokens generados para el prompt.
        
        DEPRECATED: Usar generate_async para nuevas implementaciones.
        """

    async def generate_async(
        self,
        prompt: str,
        tools_schema: list | None = None,
        user_context: dict | None = None,
    ) -> str:
        """Genera respuesta asíncrona con soporte opcional de herramientas.
        
        Args:
            prompt: El prompt completo (puede incluir system + user concatenados).
            tools_schema: Lista de definiciones de tools en formato OpenAI (opcional).
            user_context: Contexto del usuario (rol, sesión, etc.) para control de acceso.
        
        Returns:
            Respuesta generada (sin prefijos técnicos).
        
        Raises:
            NotImplementedError: Si el proveedor no implementa generación asíncrona.
        """
        raise NotImplementedError(
            f"El proveedor {self.name} no implementa generate_async. "
            "Actualizar a la interfaz asíncrona."
        )

    # Streaming opcional: proveedores pueden sobrescribirlo. Por defecto
    # simplemente delega en generate.
    def generate_stream(self, prompt: str) -> Iterable[str]:  # pragma: no cover - fallback simple
        for chunk in self.generate(prompt):
            yield chunk
