# NG-HEADER: Nombre de archivo: test_pop_email_39.py
# NG-HEADER: Ubicación: tests/test_pop_email_39.py
# NG-HEADER: Descripción: Prueba de conteo y validez de títulos en fixture POP 39 filas
# NG-HEADER: Lineamientos: Ver AGENTS.md
import re
from pathlib import Path
from services.importers.pop_email import parse_pop_email


def test_pop_39_lines_titles_and_skus():
    fixture = Path(__file__).parent / 'fixtures' / 'pop_email_39.html'
    html = fixture.read_text(encoding='utf-8')
    parsed = parse_pop_email(html, kind='html')
    assert parsed.remito_date is not None
    assert len(parsed.lines) == 39
    # Todos los títulos deben contener letras y no ser puramente numéricos
    assert all(re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", l.title) for l in parsed.lines)
    # Se deben generar SKUs POP-YYYYMMDD-###
    assert all(l.supplier_sku and l.supplier_sku.startswith("POP-") for l in parsed.lines)
