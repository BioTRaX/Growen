from __future__ import annotations

from typing import List, Tuple
from io import BytesIO
import pandas as pd
import unicodedata


class BaseSupplierParser:
    """Parser base para archivos de proveedores."""

    slug: str

    def parse(self, content: bytes) -> Tuple[List[dict], dict]:
        """Normaliza el contenido y devuelve filas y KPIs."""
        raise NotImplementedError


class SantaPlantaParser(BaseSupplierParser):
    """Parser para planillas de Santa Planta."""

    slug = "santa-planta"
    required_columns = ["ID", "Producto", "PrecioDeCompra", "PrecioDeVenta"]
    optional_columns = [
        "Agrupamiento",
        "Familia",
        "SubFamilia",
        "Compra Minima",
        "Stock",
    ]
    _synonyms = {
        "id": "ID",
        "agrupamiento": "Agrupamiento",
        "familia": "Familia",
        "subfamilia": "SubFamilia",
        "producto": "Producto",
        "compraminima": "Compra Minima",
        "stock": "Stock",
        "preciodecompra": "PrecioDeCompra",
        "preciocompra": "PrecioDeCompra",
        "preciodeventa": "PrecioDeVenta",
        "precioventa": "PrecioDeVenta",
    }

    def _norm_col(self, col: str) -> str:
        base = unicodedata.normalize("NFKD", col)
        base = "".join(ch for ch in base if not unicodedata.combining(ch))
        return base.strip().lower().replace(" ", "")

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = {c: self._synonyms.get(self._norm_col(c), c.strip()) for c in df.columns}
        return df.rename(columns=mapping)

    def parse(self, content: bytes) -> Tuple[List[dict], dict]:
        try:
            df = pd.read_excel(BytesIO(content), sheet_name="data")
        except ValueError:
            try:
                sheets = pd.read_excel(BytesIO(content), sheet_name=None)
            except Exception as e:  # noqa: BLE001
                raise ValueError("Tipo de archivo no soportado") from e
            df = None
            for sheet in sheets.values():
                sheet = self._rename_columns(sheet)
                if all(col in sheet.columns for col in self.required_columns):
                    df = sheet
                    break
            if df is None:
                raise ValueError("Hoja 'data' no encontrada")
        except Exception as e:  # noqa: BLE001
            raise ValueError("Tipo de archivo no soportado") from e
        else:
            df = self._rename_columns(df)

        missing = [c for c in self.required_columns if c not in df.columns]
        if missing:
            raise ValueError("Faltan columnas: " + ", ".join(missing))

        rows: List[dict] = []
        errors = 0
        for _, row in df.iterrows():
            code_raw = row.get("ID")
            code = "" if pd.isna(code_raw) else str(code_raw).strip()
            name_raw = row.get("Producto")
            name = "" if pd.isna(name_raw) else str(name_raw).strip()
            group = "" if pd.isna(row.get("Agrupamiento")) else str(row.get("Agrupamiento")).strip()
            family = "" if pd.isna(row.get("Familia")) else str(row.get("Familia")).strip()
            subfamily = "" if pd.isna(row.get("SubFamilia")) else str(row.get("SubFamilia")).strip()
            parts = [p for p in [group, family, subfamily] if p]
            category_path = ">".join(parts)
            cm_raw = row.get("Compra Minima")
            compra_minima = int(cm_raw) if not pd.isna(cm_raw) and str(cm_raw).strip() else 1
            pc_raw = row.get("PrecioDeCompra")
            pv_raw = row.get("PrecioDeVenta")
            precio_compra = float(pc_raw) if not pd.isna(pc_raw) else 0.0
            precio_venta = float(pv_raw) if not pd.isna(pv_raw) else 0.0

            status = "ok"
            error_msg = None
            if not name:
                status = "error"
                error_msg = "nombre vacío"
            elif not code:
                status = "error"
                error_msg = "codigo vacío"
            elif precio_compra <= 0 or precio_venta <= 0:
                status = "error"
                error_msg = "precios inválidos"

            if status == "error":
                errors += 1

            rows.append(
                {
                    "codigo": code,
                    "nombre": name,
                    "categoria_path": category_path,
                    "compra_minima": compra_minima,
                    "precio_compra": precio_compra,
                    "precio_venta": precio_venta,
                    "status": status,
                    "error_msg": error_msg,
                }
            )

        kpis = {"total": len(rows), "errors": errors}
        return rows, kpis


SUPPLIER_PARSERS = {
    SantaPlantaParser.slug: SantaPlantaParser(),
}
