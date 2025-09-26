# NG-HEADER: Nombre de archivo: types.py
# NG-HEADER: Ubicación: ai/types.py
# NG-HEADER: Descripción: Definiciones de tipos y contratos de la capa IA.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Tipos y constantes relacionados con tareas de IA."""
from enum import Enum


class Task(str, Enum):
    NLU_PARSE = "nlu.parse_command"
    NLU_INTENT = "nlu.intent"
    SHORT_ANSWER = "short_answer"
    CONTENT = "content.generation"
    SEO = "seo.product_desc"
    REASONING = "reasoning.heavy"
