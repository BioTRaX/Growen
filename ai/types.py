"""Tipos comunes usados por los proveedores de IA."""

from typing import AsyncIterator, Literal, TypedDict


class ChatMsg(TypedDict):
    """Mensaje simple para los proveedores de chat."""

    role: Literal["user", "assistant", "system"]
    content: str


class Chunk(TypedDict, total=False):
    """Chunk de texto emitido durante un stream."""

    role: Literal["assistant"]
    content: str
    done: bool


class ProviderHealth(TypedDict):
    """Estado de salud de un proveedor."""

    ok: bool
    detail: str


class FullResponse(TypedDict):
    """Respuesta completa cuando el proveedor no soporta streaming."""

    content: str


Stream = AsyncIterator[Chunk]
