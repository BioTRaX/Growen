import pandas as pd
from services.ingest import detect


def test_detecta_santa_planta(tmp_path):
    df = pd.DataFrame({
        "ID": ["1"],
        "Agrupamiento": ["A"],
        "Familia": ["F"],
        "SubFamilia": ["S"],
        "Producto": ["P"],
        "Compra Minima": [1],
        "Stock": [0],
        "PrecioDeCompra": [10],
        "PrecioDeVenta": [20],
    })
    file_path = tmp_path / "ListaPrecios_export_test.xlsx"
    df.to_excel(file_path, sheet_name="data", index=False)
    detected = detect.detect_supplier(file_path)
    assert detected == "santa-planta"
