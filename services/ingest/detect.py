# NG-HEADER: Nombre de archivo: detect.py
# NG-HEADER: Ubicación: services/ingest/detect.py
# NG-HEADER: Descripción: Detecta proveedor y tipo de archivo en la ingesta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Heurísticas básicas para detectar proveedor."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import yaml


def detect_supplier(path: str | Path) -> Optional[str]:
    """Intenta adivinar el proveedor según archivo y cabeceras."""
    path = Path(path)
    if path.suffix.lower() not in {".csv", ".xlsx"}:
        return None
    # detección específica para Santa Planta
    if "listaprecios_export" in path.name.lower():
        try:
            df = pd.read_excel(path, sheet_name="data", header=0)
        except Exception:
            return None
        expected = {
            "ID",
            "Agrupamiento",
            "Familia",
            "SubFamilia",
            "Producto",
            "Compra Minima",
            "Stock",
            "PrecioDeCompra",
            "PrecioDeVenta",
        }
        if expected.issubset(set(df.columns)):
            return "santa-planta"
    # fallback: detectar por extensión
    config_dir = Path("config/suppliers")
    for yml in config_dir.glob("*.yml"):
        with open(yml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data.get("file_type") == path.suffix.lstrip('.').lower():
            return yml.stem
    return None
