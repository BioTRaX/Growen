# NG-HEADER: Nombre de archivo: test_ingest_mapping.py
# NG-HEADER: Ubicación: tests/test_ingest_mapping.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pandas as pd
import yaml

from services.ingest import mapping


def test_resuelve_columnas_desde_yaml(tmp_path):
    with open("config/suppliers/default.yml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    df = pd.DataFrame({"Codigo": ["A1"], "Producto": ["Prob"], "Precio": ["10"]})
    mapped = mapping.map_columns(df, cfg)
    assert {"sku", "title", "price"}.issubset(mapped.columns)
