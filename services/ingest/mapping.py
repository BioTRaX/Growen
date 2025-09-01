# NG-HEADER: Nombre de archivo: mapping.py
# NG-HEADER: Ubicación: services/ingest/mapping.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Resuelve columnas externas a nombres internos."""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd


REQUIRED_FIELDS = {"supplier_product_id", "title"}


def map_columns(df: pd.DataFrame, mapping: Dict[str, Any]) -> pd.DataFrame:
    """Renombra las columnas del DataFrame según el mapeo."""
    col_map: Dict[str, str] = {}
    columns_cfg: Dict[str, list[str]] = mapping.get("columns", {})
    for internal, options in columns_cfg.items():
        for opt in options:
            if opt in df.columns:
                col_map[opt] = internal
                break
    df = df.rename(columns=col_map)
    return df


def missing_required(df: pd.DataFrame) -> set[str]:
    """Devuelve qué campos obligatorios faltan."""
    return {field for field in REQUIRED_FIELDS if field not in df.columns}
