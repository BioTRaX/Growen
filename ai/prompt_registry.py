#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: prompt_registry.py
# NG-HEADER: Ubicación: ai/prompt_registry.py
# NG-HEADER: Descripción: Registro en memoria de prompts activos respaldados por PostgreSQL.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Caché de lectura para prompts activos y trazabilidad por respuesta.

PostgreSQL continúa siendo la fuente de verdad. El caché evita hacer I/O desde
``get_persona_prompt``, que forma parte de una interfaz sincrónica.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class ActivePrompt:
    id: int
    prompt_key: str
    version: int
    content: str


_lock = RLock()
_active: dict[str, ActivePrompt] = {}
_selected: ContextVar[ActivePrompt | None] = ContextVar("selected_prompt", default=None)


def replace_active(prompts: list[ActivePrompt]) -> None:
    with _lock:
        _active.clear()
        _active.update({prompt.prompt_key: prompt for prompt in prompts})


def activate(prompt: ActivePrompt) -> None:
    with _lock:
        _active[prompt.prompt_key] = prompt


def resolve(prompt_key: str, fallback: str) -> str:
    with _lock:
        prompt = _active.get(prompt_key)
    _selected.set(prompt)
    return prompt.content if prompt else fallback


def selected_metadata() -> dict[str, int | str]:
    prompt = _selected.get()
    if prompt is None:
        return {"prompt_source": "code_fallback"}
    return {"prompt_version_id": prompt.id, "prompt_key": prompt.prompt_key, "prompt_version": prompt.version}
