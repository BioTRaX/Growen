from io import BytesIO
import pandas as pd

REQUIRED = {"ID", "Producto", "PrecioDeCompra", "PrecioDeVenta"}
OPTIONAL = {"Agrupamiento", "Familia", "SubFamilia", "Compra Minima", "Stock"}


class BaseSupplierParser:
    slug: str

    def parse_bytes(self, b: bytes) -> list[dict]:
        raise NotImplementedError


class SantaPlantaParser(BaseSupplierParser):
    slug = "santa-planta"

    def parse_bytes(self, b: bytes) -> list[dict]:
        try:
            df = pd.read_excel(BytesIO(b), sheet_name="data")
        except Exception:
            sheets = pd.read_excel(BytesIO(b), sheet_name=None)
            def normalize_cols(c):
                return [str(x).strip() for x in c]
            for name, sdf in sheets.items():
                cols = set(normalize_cols(sdf.columns))
                if REQUIRED.issubset(cols):
                    df = sdf
                    break
            else:
                raise ValueError(
                    "Hoja 'data' no encontrada y no se halló hoja con columnas requeridas"
                )

        df.columns = [str(c).strip() for c in df.columns]
        missing = REQUIRED - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas: {', '.join(sorted(missing))}")

        rows = []
        for _, r in df.iterrows():
            codigo = str(r["ID"]).strip() if pd.notna(r.get("ID")) else ""
            nombre = str(r["Producto"]).strip() if pd.notna(r.get("Producto")) else ""
            agr = str(r.get("Agrupamiento") or "").strip()
            fam = str(r.get("Familia") or "").strip()
            sub = str(r.get("SubFamilia") or "").strip()
            path = " > ".join([x for x in [agr, fam, sub] if x])

            try:
                pc = float(r.get("PrecioDeCompra") or 0)
            except Exception:
                pc = 0.0
            try:
                pv = float(r.get("PrecioDeVenta") or 0)
            except Exception:
                pv = 0.0

            try:
                cm = int(r.get("Compra Minima") or 1)
            except Exception:
                cm = 1

            status, err = "ok", None
            if not codigo or not nombre:
                status, err = "error", "codigo/nombre vacío"
            elif pc <= 0 or pv <= 0:
                status, err = "error", "precio_compra/venta <= 0"

            rows.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "categoria_path": path,
                    "compra_minima": cm,
                    "precio_compra": pc,
                    "precio_venta": pv,
                    "status": status,
                    "error_msg": err,
                }
            )
        return rows


SUPPLIER_PARSERS = {SantaPlantaParser.slug: SantaPlantaParser()}
