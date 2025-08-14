"""Heurísticas básicas para detectar proveedor."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def detect_supplier(path: str | Path) -> Optional[str]:
    """Intenta adivinar el proveedor según el encabezado."""
    path = Path(path)
    if path.suffix.lower() not in {".csv", ".xlsx"}:
        return None
    config_dir = Path("config/suppliers")
    for yml in config_dir.glob("*.yml"):
        with open(yml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data.get("file_type") == path.suffix.lstrip('.').lower():
            return yml.stem
    return None
