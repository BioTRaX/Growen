#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_openai_provider.py
# NG-HEADER: Ubicación: tests/test_openai_provider.py
# NG-HEADER: Descripción: Pruebas de OpenAIProvider (fallback y tono)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os

from ai.providers.openai_provider import OpenAIProvider
from ai.persona import SYSTEM_PROMPT


def test_openai_provider_fallback_no_key(monkeypatch):
    """Si falta OPENAI_API_KEY debe devolver eco con prefijo openai:."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIProvider()
    user_prompt = "Explicá brevemente qué es un SKU"
    full = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    out = "".join(p.generate(full))
    assert out.startswith("openai:")
    # Debe contener parte del system prompt (tono rioplatense)
    assert "sarcástico" in out.lower() or "rioplatense" in out.lower()
