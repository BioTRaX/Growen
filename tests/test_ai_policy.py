# NG-HEADER: Nombre de archivo: test_ai_policy.py
# NG-HEADER: Ubicación: tests/test_ai_policy.py
# NG-HEADER: Descripción: Pruebas de la política de ruteo entre modelos IA.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from unittest.mock import patch
from ai.policy import choose
from ai.types import Task
from agent_core.config import Settings


def test_policy_auto():
    """Test de ruteo automático según configuración de AI_MODE en .env"""
    settings = Settings()
    
    # Si el .env tiene AI_MODE=openai, el ruteo será diferente al default "auto"
    # Verificamos que choose respeta la configuración del usuario
    ai_mode = os.getenv("AI_MODE", "auto")
    
    if ai_mode == "openai":
        # Usuario configuró OpenAI: todas las tareas van a openai
        assert choose(Task.NLU_PARSE.value, settings) == "openai"
        assert choose(Task.CONTENT.value, settings) == "openai"
    elif ai_mode == "ollama":
        # Usuario configuró Ollama: todas las tareas van a ollama
        assert choose(Task.NLU_PARSE.value, settings) == "ollama"
        assert choose(Task.CONTENT.value, settings) == "ollama"
    else:
        # Modo auto (default): tareas se rutean según política interna
        assert choose(Task.NLU_PARSE.value, settings) == "ollama"
        assert choose(Task.CONTENT.value, settings) == "openai"


def test_policy_override():
    settings = Settings(ai_mode="openai")
    assert choose(Task.NLU_PARSE.value, settings) == "openai"
    settings = Settings(ai_mode="ollama")
    assert choose(Task.CONTENT.value, settings) == "ollama"
