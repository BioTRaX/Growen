from __future__ import annotations

from typing import List

import pandas as pd


class BaseSupplierParser:
    """Parser base para archivos de proveedores."""

    slug: str
    required_columns: List[str]

    def parse_df(self, df: pd.DataFrame) -> List[dict]:
        """Normaliza el DataFrame a una lista de dicts homogéneos."""
        raise NotImplementedError


class SantaPlantaParser(BaseSupplierParser):
    """Parser para planillas de Santa Planta."""

    slug = "santaplanta"
    required_columns = [
        "ID",
        "Producto",
        "Agrupamiento",
        "Familia",
        "SubFamilia",
        "Compra Minima",
        "PrecioDeCompra",
        "PrecioDeVenta",
    ]

    def parse_df(self, df: pd.DataFrame) -> List[dict]:
        missing = [c for c in self.required_columns if c not in df.columns]
        if missing:
            raise ValueError(f"Columnas faltantes: {missing}")

        rows: List[dict] = []
        for _, row in df.iterrows():
            parts = [
                str(row.get("Agrupamiento", "")).strip(),
                str(row.get("Familia", "")).strip(),
                str(row.get("SubFamilia", "")).strip(),
            ]
            category_path = ">".join([p for p in parts if p])
            data = {
                "codigo": str(row["ID"]).strip(),
                "nombre": str(row["Producto"]).strip(),
                "categoria_path": category_path,
                "compra_minima": int(row.get("Compra Minima") or 1),
                "precio_compra": float(row.get("PrecioDeCompra") or 0),
                "precio_venta": float(row.get("PrecioDeVenta") or 0),
            }
            rows.append(data)
        return rows


SUPPLIER_PARSERS = {
    SantaPlantaParser.slug: SantaPlantaParser(),
}
