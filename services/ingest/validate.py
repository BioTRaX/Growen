"""Validaciones simples de filas."""
from __future__ import annotations

from typing import Dict, Any, Tuple


def validate_row(row: Dict[str, Any]) -> Tuple[bool, str | None]:
    """Valida campos mínimos."""
    if not row.get("title"):
        return False, "title requerido"
    price = row.get("price")
    if price is not None and price < 0:
        return False, "price negativo"
    return True, None
