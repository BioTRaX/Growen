# NG-HEADER: Nombre de archivo: test_pop_email_parser.py
# NG-HEADER: Ubicación: tests/test_pop_email_parser.py
# NG-HEADER: Descripción: Pruebas del parser de emails POP (heurísticas de títulos y extracción)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import re
from services.importers.pop_email import parse_pop_email, _clean_title_pop, _title_is_valid_pop


def test_clean_title_pop():
    raw = "Comprar por: x 3 Shampoo Coco - x 2 Tamaño:10cm"
    cleaned = _clean_title_pop(raw)
    assert "Comprar" not in cleaned
    assert "Tamaño" not in cleaned
    assert not cleaned.strip().endswith("x 2")
    assert "Shampoo" in cleaned


def test_title_is_valid_pop():
    assert _title_is_valid_pop("Shampoo Coco") is True
    assert _title_is_valid_pop("12345") is False
    assert _title_is_valid_pop("Kit x 3") is False


def test_parse_html_table_prefers_letter_dense_title_column():
    html = """
    <table>
      <tr><th>ID</th><th>Detalle</th><th>Cantidad</th></tr>
      <tr><td>1001</td><td>Shampoo Coco Hidratante - x 6</td><td>2</td></tr>
      <tr><td>1002</td><td>Acondicionador Argan Nutritivo</td><td>1</td></tr>
    </table>
    """
    parsed = parse_pop_email(html, kind='html')
    assert parsed.lines, "Debe extraer líneas"
    assert all(l.title and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", l.title) for l in parsed.lines)
    # Debe limpiar sufijo de pack
    assert not any(t.strip().endswith("x 6") for t in [l.title for l in parsed.lines])


def test_parse_text_lines_and_remito_from_text():
    text = "Pedido 488344 Completado\nShampoo Coco x 2 $ 1.234,50\nKit Cepillos x 3\nTel: 555-1234"
    parsed = parse_pop_email(text, kind='text')
    assert parsed.remito_number == "488344"
    assert len(parsed.lines) >= 2
    assert any("Shampoo" in l.title for l in parsed.lines)
    assert all(l.supplier_sku and l.supplier_sku.startswith("POP-") for l in parsed.lines)
