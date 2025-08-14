"""Proveedor basado en la API de OpenAI."""

from __future__ import annotations

import json
import os
from typing import AsyncIterator

import httpx

from ..provider_base import ILLMProvider
from ..types import ChatMsg, Chunk, FullResponse, ProviderHealth


class OpenAIProvider(ILLMProvider):
    """Uso de Chat Completions de OpenAI."""

    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout = int(os.getenv("AI_TIMEOUT_OPENAI_MS", "60000")) / 1000
        self.base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def supports(self, stream: bool, modality: str) -> bool:  # pragma: no cover - simple
        return modality == "text"

    async def acomplete(
        self, messages: list[ChatMsg], stream: bool = True, **_: dict
    ) -> AsyncIterator[Chunk] | FullResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {"model": self.model, "messages": messages, "stream": stream}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if stream:
                async with client.stream(
                    "POST", f"{self.base}/chat/completions", json=payload, headers=headers
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        if line.strip() == "data: [DONE]":
                            yield Chunk(role="assistant", content="", done=True)
                            break
                        data = json.loads(line[len("data: ") :])
                        delta = data["choices"][0]["delta"].get("content", "")
                        yield Chunk(role="assistant", content=delta, done=False)
            else:
                resp = await client.post(
                    f"{self.base}/chat/completions", json=payload, headers=headers
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return FullResponse(content=content)

    async def healthcheck(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth(ok=False, detail="missing api key")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base}/models", headers={"Authorization": f"Bearer {self.api_key}"})
                ok = resp.status_code == 200
                detail = "ok" if ok else resp.text
        except Exception as exc:  # pragma: no cover - fallo de red
            ok = False
            detail = str(exc)
        return ProviderHealth(ok=ok, detail=detail)
