"""Fachada que decide proveedor, ejecuta y aplica fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Literal

from .policy import choose_provider, Task
from .provider_base import ILLMProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider
from .types import ChatMsg, Chunk, FullResponse

logger = logging.getLogger(__name__)

_providers: dict[str, ILLMProvider] | None = None


def _get_providers() -> dict[str, ILLMProvider]:
    global _providers
    if _providers is None:
        _providers = {"ollama": OllamaProvider(), "openai": OpenAIProvider()}
    return _providers


async def _run_provider(
    provider: ILLMProvider, messages: list[ChatMsg], stream: bool
) -> AsyncIterator[Chunk]:
    result = await provider.acomplete(messages, stream=stream)
    if hasattr(result, "__aiter__"):  # pragma: no cover - generador
        return result

    async def _single() -> AsyncIterator[Chunk]:  # pragma: no cover
        yield Chunk(role="assistant", content=result["content"], done=True)

    return _single()


async def complete(
    task: Task, messages: list[ChatMsg], stream: bool = True, context: dict | None = None
) -> AsyncIterator[Chunk]:
    context = context or {}
    providers = _get_providers()
    primary_name = choose_provider(task, context)
    primary = providers[primary_name]
    secondary = providers["openai" if primary_name == "ollama" else "ollama"]

    try:
        logger.info("task=%s provider=%s", task, primary.name)
        async for chunk in await _run_provider(primary, messages, stream):
            yield chunk
        return
    except Exception as exc:  # pragma: no cover - fallo primario
        logger.warning("fallback to %s due to %s", secondary.name, exc)
        yield Chunk(
            role="assistant",
            content="Cambié a proveedor alternativo por error.",
            done=False,
        )
        async for chunk in await _run_provider(secondary, messages, stream):
            yield chunk
