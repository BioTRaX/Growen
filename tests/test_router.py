import types

import pytest

from ai import ChatMsg
from ai.router import complete


class DummyProvider:
    name = "ollama"

    async def acomplete(self, messages, stream=True, **kwargs):
        async def gen():
            yield {"role": "assistant", "content": "hola", "done": True}
        return gen()

    def supports(self, stream: bool, modality: str) -> bool:
        return True

    async def healthcheck(self):
        return {"ok": True, "detail": "ok"}


class FailingProvider(DummyProvider):
    name = "openai"

    async def acomplete(self, messages, stream=True, **kwargs):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_router_fallback(monkeypatch):
    from ai import router

    monkeypatch.setattr(
        router, "_get_providers", lambda: {"openai": FailingProvider(), "ollama": DummyProvider()}
    )
    messages = [ChatMsg(role="user", content="hola")]
    gen = complete("content.generation", messages, stream=True)
    chunks = [chunk async for chunk in gen]
    assert any("alternativo" in c["content"] for c in chunks)
