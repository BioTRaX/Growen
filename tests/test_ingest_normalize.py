import pandas as pd

from services.ingest import normalize


def test_reemplaza_coma_decimal():
    df = pd.DataFrame({"price": ["10,50"]})
    cfg = {"transform": {"price": {"replace_comma_decimal": True}}}
    out = normalize.apply(df, cfg)
    assert float(out.loc[0, "price"]) == 10.50
