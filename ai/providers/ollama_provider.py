"""Proveedor local basado en Ollama."""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

import httpx

from ..provider_base import ILLMProvider
from ..types import ChatMsg, Chunk, FullResponse, ProviderHealth


class OllamaProvider(ILLMProvider):
    """Implementación simple contra la API HTTP de Ollama."""

    name = "ollama"

    def __init__(self) -> None:
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")
        self.timeout = int(os.getenv("AI_TIMEOUT_OLLAMA_MS", "12000")) / 1000

    def supports(self, stream: bool, modality: str) -> bool:  # pragma: no cover - simple
        return modality == "text"

    async def acomplete(
        self, messages: list[ChatMsg], stream: bool = True, **_: dict
    ) -> AsyncIterator[Chunk] | FullResponse:
        payload = {"model": self.model, "messages": messages, "stream": stream}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if stream:
                async with client.stream(
                    "POST", f"{self.host}/api/chat", json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        yield Chunk(
                            role="assistant",
                            content=data.get("message", {}).get("content", ""),
                            done=data.get("done", False),
                        )
            else:
                resp = await client.post(f"{self.host}/api/chat", json=payload)
                data = resp.json()
                return FullResponse(
                    content=data.get("message", {}).get("content", "")
                )

    async def healthcheck(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.host}/api/tags")
                ok = resp.status_code == 200
                detail = "ok" if ok else resp.text
        except Exception as exc:  # pragma: no cover - fallo de red
            ok = False
            detail = str(exc)
        return ProviderHealth(ok=ok, detail=detail)
