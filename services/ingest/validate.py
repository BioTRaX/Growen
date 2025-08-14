"""Validaciones simples de filas."""
from __future__ import annotations

from typing import Any, Dict, Tuple


def validate_row(row: Dict[str, Any]) -> Tuple[bool, str | None]:
    """Valida campos mínimos para productos de proveedor."""
    if not row.get("supplier_product_id"):
        return False, "supplier_product_id requerido"
    if not row.get("title"):
        return False, "title requerido"
    price = row.get("purchase_price")
    if price is not None and price < 0:
        return False, "purchase_price negativo"
    return True, None
