# NG-HEADER: Nombre de archivo: rules_engine.py
# NG-HEADER: Ubicación: agent_core/rules_engine.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Motor de reglas simple para evaluar condiciones del agente."""
from typing import Any, Callable


class RulesEngine:
    """Ejecutor trivial de reglas representadas como callables."""

    def __init__(self) -> None:
        self._rules: list[Callable[[Any], bool]] = []

    def add_rule(self, rule: Callable[[Any], bool]) -> None:
        self._rules.append(rule)

    def evaluate(self, context: Any) -> bool:
        return all(rule(context) for rule in self._rules)
