# NG-HEADER: Nombre de archivo: bus.py
# NG-HEADER: Ubicación: agent_core/bus.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Bus de eventos en memoria."""
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List


class EventBus:
    """Sistema de publicación/suscripción extremadamente simple."""

    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        self._subs[event].append(handler)

    def publish(self, event: str, payload: Any) -> None:
        for handler in self._subs.get(event, []):
            handler(payload)
