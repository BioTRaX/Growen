"""Funciones de limpieza de datos."""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def apply(df: pd.DataFrame, mapping: Dict[str, Any]) -> pd.DataFrame:
    """Aplica transformaciones básicas al DataFrame."""
    transforms: Dict[str, Dict[str, Any]] = mapping.get("transform", {})
    for field, rules in transforms.items():
        if field not in df.columns:
            continue
        if rules.get("replace_comma_decimal"):
            df[field] = (
                df[field]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[field] = pd.to_numeric(df[field], errors="coerce")
    return df
