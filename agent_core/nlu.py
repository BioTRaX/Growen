# NG-HEADER: Nombre de archivo: nlu.py
# NG-HEADER: Ubicación: agent_core/nlu.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Utilidades de NLU básicas."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


COMMAND_RE = re.compile(r"^/(?P<cmd>\w+)(?P<args>.*)$")


@dataclass
class ParsedCommand:
    command: str
    args: str = ""


def parse(text: str) -> Optional[ParsedCommand]:
    """Parsea mensajes que comienzan con `/`."""
    match = COMMAND_RE.match(text.strip())
    if not match:
        return None
    return ParsedCommand(match.group("cmd"), match.group("args").strip())
