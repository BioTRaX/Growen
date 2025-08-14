"""Definiciones base para los proveedores de LLM."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from .types import ChatMsg, Chunk, FullResponse, ProviderHealth


@runtime_checkable
class ILLMProvider(Protocol):
    """Interfaz requerida por todos los proveedores."""

    name: str

    def supports(self, stream: bool, modality: str) -> bool:
        """Indica si el proveedor soporta el modo solicitado."""

    async def acomplete(
        self, messages: list[ChatMsg], **kwargs
    ) -> AsyncIterator[Chunk] | FullResponse:
        """Realiza una completion de manera asíncrona."""

    async def healthcheck(self) -> ProviderHealth:
        """Devuelve el estado de salud del proveedor."""
