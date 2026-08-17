# NG-HEADER: Nombre de archivo: test_ai_router.py
# NG-HEADER: Ubicación: tests/test_ai_router.py
# NG-HEADER: Descripción: Pruebas del router de intents IA.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest

from ai.router import AIRouter
from ai.providers.ollama_provider import OllamaUnavailableError
from ai.types import Task
from agent_core.config import Settings


def test_router_openai_when_allowed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "ai.providers.openai_provider.OpenAIProvider.generate",
        lambda self, prompt: ["openai:stub"],
    )
    router = AIRouter(Settings(ai_allow_external=True))
    assert "openai" in router.available_providers()
    out = router.run(Task.CONTENT.value, "hola")
    assert out.startswith("openai:")


def test_router_fails_closed_without_external(monkeypatch):
    monkeypatch.delenv("AI_DISABLE_OLLAMA", raising=False)
    monkeypatch.setattr(
        "ai.providers.ollama_provider.OllamaProvider.generate",
        lambda self, prompt: (_ for _ in ()).throw(
            OllamaUnavailableError("ollama_generation_unavailable")
        ),
    )
    router = AIRouter(Settings(ai_allow_external=False))
    assert router.available_providers() == ["ollama"]
    with pytest.raises(OllamaUnavailableError, match="ollama_generation_unavailable"):
        router.run(Task.CONTENT.value, "hola")
