"""Carga archivos CSV/XLSX usando pandas."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd


def load_file(path: str | Path, mapping: Dict[str, Any]) -> pd.DataFrame:
    """Lee un archivo de proveedor según la configuración dada."""
    path = Path(path)
    file_type = mapping.get("file_type", "csv").lower()
    if file_type == "csv":
        return pd.read_csv(
            path,
            encoding=mapping.get("encoding", "utf-8"),
            delimiter=mapping.get("delimiter", ","),
        )
    if file_type == "xlsx":
        return pd.read_excel(
            path,
            sheet_name=mapping.get("sheet_name"),
            header=mapping.get("header_row", 1) - 1,
        )
    raise ValueError(f"Tipo de archivo no soportado: {file_type}")
