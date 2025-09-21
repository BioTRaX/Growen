# NG-HEADER: Nombre de archivo: test_price_intent.py
# NG-HEADER: Ubicación: tests/test_price_intent.py
# NG-HEADER: Descripción: Pruebas unitarias para el intent de precios
# NG-HEADER: Lineamientos: Ver AGENTS.md
from services.chat.price_lookup import extract_price_query


def test_extract_price_basic():
    assert extract_price_query("precio del sustrato premium") == "sustrato premium"
    assert extract_price_query("Cuál es el precio de la carpa 80x80?") == "carpa 80x80"
    assert extract_price_query("cuanto sale fertilizante liquido") == "fertilizante liquido"


def test_extract_price_handles_articles_and_punctuation():
    assert extract_price_query("Precio de la Podadora Gamma!!!").lower() == "podadora gamma"
    assert extract_price_query("Cuanto vale el Grow Box 120?").lower() == "grow box 120"
    assert extract_price_query("Me decís cuanto cuesta, porfa?") is None
