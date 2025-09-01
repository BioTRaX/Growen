# NG-HEADER: Nombre de archivo: test_ai_policy.py
# NG-HEADER: Ubicación: tests/test_ai_policy.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from ai.policy import choose
from ai.types import Task
from agent_core.config import Settings


def test_policy_auto():
    settings = Settings()
    assert choose(Task.NLU_PARSE.value, settings) == "ollama"
    assert choose(Task.CONTENT.value, settings) == "openai"


def test_policy_override():
    settings = Settings(ai_mode="openai")
    assert choose(Task.NLU_PARSE.value, settings) == "openai"
    settings = Settings(ai_mode="ollama")
    assert choose(Task.CONTENT.value, settings) == "ollama"
