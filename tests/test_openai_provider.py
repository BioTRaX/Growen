#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_openai_provider.py
# NG-HEADER: Ubicación: tests/test_openai_provider.py
# NG-HEADER: Descripción: Pruebas de OpenAIProvider (fallback y tono)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest

from ai.providers.openai_provider import OpenAIProvider
from ai.persona import SYSTEM_PROMPT


def test_openai_provider_fails_closed_without_key(monkeypatch):
    """Si falta la clave, el proveedor no debe devolver el prompt como respuesta."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    p = OpenAIProvider()
    user_prompt = "Explicá brevemente qué es un SKU"
    full = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    with pytest.raises(RuntimeError, match="openai_provider_unavailable"):
        "".join(p.generate(full))


def test_openai_provider_reads_key_file(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    key_file = tmp_path / "openai_api_key"
    key_file.write_text("test-file-key\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY_FILE", str(key_file.resolve()))

    provider = OpenAIProvider()

    assert provider.api_key == "test-file-key"


@pytest.mark.asyncio
async def test_openai_vision_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    monkeypatch.setenv("OPENAI_VISION_ENABLED", "0")
    provider = OpenAIProvider()

    with pytest.raises(RuntimeError, match="openai_vision_disabled"):
        await provider.generate_async("diagnóstico", images=["https://example.invalid/image.png"])
