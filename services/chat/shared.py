# NG-HEADER: Nombre de archivo: shared.py
# NG-HEADER: Ubicacion: services/chat/shared.py
# NG-HEADER: Descripcion: Constantes y funciones compartidas para el chatbot de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Constantes y helpers compartidos por HTTP y WebSocket del chatbot."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from services.chat.price_lookup import ProductQuery

ALLOWED_PRODUCT_INTENT_ROLES = {"admin", "colaborador", "cliente"}
ALLOWED_PRODUCT_METRIC_ROLES = {"admin"}

CLARIFY_CONFIRM_WORDS = {
    "si",
    "dale",
    "ok",
    "okay",
    "vale",
    "mostrar",
    "mostrame",
    "mostra",
    "mostralo",
    "mostrarlo",
    "precios",
    "precio",
    "stock",
    "dale si",
}


def normalize_followup_text(value: str) -> str:
    """Normaliza texto corto para detectar confirmaciones o nuevas consultas."""

    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = ascii_text.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _join_terms(terms: Iterable[str]) -> str:
    return " ".join(t for t in terms if t)


def memory_terms_text(query: ProductQuery) -> str:
    """Devuelve texto representativo de la consulta almacenada en memoria."""

    if query.terms:
        return _join_terms(query.terms)
    if query.normalized_text:
        return query.normalized_text
    return query.raw_text


def clarify_prompt_text(memory_terms: str) -> str:
    """Mensaje de aclaracion utilizado cuando la respuesta precisa confirmacion."""

    focus = memory_terms or "la consulta"
    return f"Seguimos con {focus}. Queres que te muestre precios y stock?"
