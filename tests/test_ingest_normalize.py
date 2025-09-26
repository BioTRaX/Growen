# NG-HEADER: Nombre de archivo: test_ingest_normalize.py
# NG-HEADER: Ubicación: tests/test_ingest_normalize.py
# NG-HEADER: Descripción: Pruebas de la normalización en la ingesta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pandas as pd

from services.ingest import normalize


def test_reemplaza_coma_decimal():
    df = pd.DataFrame({"price": ["10,50"]})
    cfg = {"transform": {"price": {"replace_comma_decimal": True}}}
    out = normalize.apply(df, cfg)
    assert float(out.loc[0, "price"]) == 10.50
