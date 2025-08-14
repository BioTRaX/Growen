import pandas as pd
import yaml
from services.ingest import mapping


def test_mapeo_campos_santa_planta():
    with open("config/suppliers/santa-planta.yml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    df = pd.DataFrame({
        "ID": ["1"],
        "Producto": ["P"],
        "Agrupamiento": ["A"],
        "Familia": ["F"],
        "SubFamilia": ["S"],
        "Compra Minima": [1],
        "Stock": [0],
        "PrecioDeCompra": [10],
        "PrecioDeVenta": [20],
    })
    mapped = mapping.map_columns(df, cfg)
    assert {"supplier_product_id", "title", "purchase_price", "sale_price"}.issubset(mapped.columns)
