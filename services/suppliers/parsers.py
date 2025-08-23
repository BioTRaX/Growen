"""Parsers de listas de precios de proveedores.

Este módulo expone un parser genérico basado en archivos Excel/CSV
configurable mediante archivos YAML ubicados en ``config/suppliers``.
También permite agregar parsers personalizados a través de
``entry_points`` del grupo ``growen.suppliers.parsers`` y expone
``SUPPLIER_PARSERS`` con todas las instancias registradas.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

import os
from rapidfuzz import fuzz, process
import pandas as pd
import yaml

# objetos visibles al importar el módulo
__all__ = [
    "BaseSupplierParser",
    "GenericExcelParser",
    "SUPPLIER_PARSERS",
    "AUTO_CREATE_CANONICAL",
    "FUZZY_SUGGESTION_THRESHOLD",
    "suggest_canonicals",
]

# valores de configuración provenientes de variables de entorno
AUTO_CREATE_CANONICAL = os.getenv("AUTO_CREATE_CANONICAL", "true").lower() == "true"
FUZZY_SUGGESTION_THRESHOLD = float(os.getenv("FUZZY_SUGGESTION_THRESHOLD", "0.87"))
SUGGESTION_CANDIDATES = int(os.getenv("SUGGESTION_CANDIDATES", "3"))


def suggest_canonicals(name: str, choices: dict[int, str]) -> list[dict]:
    """Obtiene sugerencias de canónicos similares con ``rapidfuzz``.

    Se compara ``name`` con cada entrada de ``choices`` y se devuelven
    las mejores coincidencias cuyo puntaje supera ``FUZZY_SUGGESTION_THRESHOLD``.

    Args:
        name: nombre a comparar.
        choices: diccionario ``{id: nombre}`` de canónicos existentes.

    Returns:
        Lista de diccionarios con ``id``, ``name`` y ``score`` (0 a 1).
    """

    matches = process.extract(
        name,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=FUZZY_SUGGESTION_THRESHOLD * 100,
        limit=SUGGESTION_CANDIDATES,
    )
    return [
        {"id": key, "name": choices[key], "score": score / 100}
        for _, score, key in matches
    ]


class BaseSupplierParser:
    """Interfaz mínima que deben implementar todos los parsers."""

    slug: str

    def parse_bytes(self, b: bytes) -> list[dict]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class GenericExcelParser(BaseSupplierParser):
    """Parser configurable por YAML para planillas simples.

    Cada archivo ``*.yml`` describe cómo mapear las columnas externas a
    campos internos y qué transformaciones aplicar. El atributo ``slug``
    se toma del propio YAML o del nombre del archivo.
    """

    slug: str
    config: Dict[str, Any]

    def parse_bytes(self, b: bytes) -> list[dict]:
        cfg = self.config

        stream = BytesIO(b)
        ftype = cfg.get("file_type", "xlsx").lower()
        if ftype == "xlsx":
            df = pd.read_excel(
                stream,
                sheet_name=cfg.get("sheet_name"),
                header=cfg.get("header_row", 0),
            )
        elif ftype == "csv":
            df = pd.read_csv(
                stream,
                delimiter=cfg.get("delimiter", ","),
                encoding=cfg.get("encoding", "utf-8"),
                header=cfg.get("header_row", 0),
            )
        else:  # pragma: no cover - validado por configuración
            raise ValueError("Tipo de archivo no soportado")

        # normalizar encabezados
        df.columns = [str(c).strip() for c in df.columns]

        # resolver mapeos de columnas
        col_map: Dict[str, str] = {}
        for internal, options in cfg.get("columns", {}).items():
            for opt in options:
                if opt in df.columns:
                    col_map[opt] = internal
                    break
        df = df.rename(columns=col_map)

        required = {"supplier_product_id", "title", "purchase_price", "sale_price"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas: {', '.join(sorted(missing))}")

        # aplicar transformaciones básicas
        for field, opts in cfg.get("transform", {}).items():
            if opts.get("replace_comma_decimal") and field in df.columns:
                df[field] = df[field].map(
                    lambda v: str(v).replace(",", ".") if pd.notna(v) else v
                )

        defaults = cfg.get("defaults", {})

        rows: list[dict] = []
        for _, r in df.iterrows():
            codigo = str(r.get("supplier_product_id") or "").strip()
            nombre = str(r.get("title") or "").strip()

            cat_parts = [
                str(r.get("category_level_1") or "").strip(),
                str(r.get("category_level_2") or "").strip(),
                str(r.get("category_level_3") or "").strip(),
            ]
            categoria_path = " > ".join([p for p in cat_parts if p])

            try:
                pc = float(r.get("purchase_price") or 0)
            except Exception:  # pragma: no cover - defensivo
                pc = 0.0
            try:
                pv = float(r.get("sale_price") or 0)
            except Exception:  # pragma: no cover - defensivo
                pv = 0.0

            try:
                cm_raw = r.get("min_purchase_qty")
                cm = int(cm_raw if pd.notna(cm_raw) else defaults.get("min_qty", 1))
            except Exception:  # pragma: no cover - defensivo
                cm = int(defaults.get("min_qty", 1))

            status, err = "ok", None
            if not codigo or not nombre:
                status, err = "error", "codigo/nombre vacío"
            elif pc <= 0 or pv <= 0:
                status, err = "error", "precio_compra/venta <= 0"

            rows.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "categoria_path": categoria_path,
                    "compra_minima": cm,
                    "precio_compra": pc,
                    "precio_venta": pv,
                    "status": status,
                    "error_msg": err,
                }
            )

        return rows


def _load_yaml_parsers() -> dict[str, BaseSupplierParser]:
    """Crea instancias del parser genérico para cada YAML configurado."""

    parsers: dict[str, BaseSupplierParser] = {}
    config_dir = Path("config/suppliers")
    for yml in config_dir.glob("*.yml"):
        with open(yml, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        slug = cfg.get("slug") or yml.stem
        parsers[slug] = GenericExcelParser(slug=slug, config=cfg)
    return parsers


# parsers declarados por YAML
SUPPLIER_PARSERS = _load_yaml_parsers()


# parsers extra que se registren mediante entry_points
try:  # pragma: no cover - dependemos de la versión de importlib
    eps = entry_points(group="growen.suppliers.parsers")
except TypeError:  # pragma: no cover - compatibilidad
    eps = entry_points().get("growen.suppliers.parsers", [])

for ep in eps:
    obj = ep.load()
    parser = obj() if isinstance(obj, type) else obj
    if isinstance(parser, BaseSupplierParser):
        SUPPLIER_PARSERS[parser.slug] = parser

