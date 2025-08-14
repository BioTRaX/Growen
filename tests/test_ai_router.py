from ai.router import AIRouter
from ai.types import Task
from agent_core.config import Settings


def test_router_openai_when_allowed():
    router = AIRouter(Settings())
    assert "openai" in router.available_providers()
    out = router.run(Task.CONTENT.value, "hola")
    assert out.startswith("openai:")


def test_router_falls_back_without_external():
    router = AIRouter(Settings(ai_allow_external=False))
    assert router.available_providers() == ["ollama"]
    out = router.run(Task.CONTENT.value, "hola")
    assert out.startswith("ollama:")
