# NG-HEADER: Nombre de archivo: test_ai_router.py
# NG-HEADER: Ubicación: tests/test_ai_router.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from ai.router import AIRouter
from ai.types import Task
from agent_core.config import Settings


def test_router_openai_when_allowed():
    router = AIRouter(Settings())
    assert "openai" in router.available_providers()
    out = router.run(Task.CONTENT.value, "hola")
    assert out.startswith("openai:")


def test_router_falls_back_without_external():
    # Asegurar que ollama esté habilitado para esta prueba
    os.environ.pop("AI_DISABLE_OLLAMA", None)
    router = AIRouter(Settings(ai_allow_external=False))
    assert router.available_providers() == ["ollama"]
    out = router.run(Task.CONTENT.value, "hola")
    assert out.startswith("ollama:") or out == "hola"
