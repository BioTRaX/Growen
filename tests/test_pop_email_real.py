# NG-HEADER: Nombre de archivo: test_pop_email_real.py
# NG-HEADER: Ubicación: tests/test_pop_email_real.py
# NG-HEADER: Descripción: Prueba opcional con fixture real (anonimizado) de POP
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import re
from pathlib import Path
import pytest
from services.importers.pop_email import parse_pop_email


@pytest.mark.skipif(
    not (
        Path(__file__).parent / 'fixtures' / 'pop_email_real.eml'
    ).exists() and not (
        Path(__file__).parent / 'fixtures' / 'pop_email_real.html'
    ).exists() and not os.getenv('POP_REAL_FIXTURE'),
    reason="No se encontró fixture real de POP (tests/fixtures/pop_email_real.(eml|html) o var POP_REAL_FIXTURE)"
)
@pytest.mark.parametrize("kind, path", [
    ("eml", Path(__file__).parent / 'fixtures' / 'pop_email_real.eml'),
    ("html", Path(__file__).parent / 'fixtures' / 'pop_email_real.html'),
])
def test_pop_email_real_fixture(kind, path):
    if os.getenv('POP_REAL_FIXTURE'):
        path = Path(os.getenv('POP_REAL_FIXTURE'))
        if path.suffix.lower() == '.eml':
            kind = 'eml'
        elif path.suffix.lower() in ('.htm', '.html'):
            kind = 'html'
        else:
            kind = 'text'
    if not path.exists():
        pytest.skip(f"No existe fixture {path}")
    data = path.read_bytes() if kind == 'eml' else path.read_text(encoding='utf-8', errors='ignore')
    parsed = parse_pop_email(data, kind=kind)
    assert parsed.lines, "Debe extraer al menos alguna línea real"
    assert all(l.title and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", l.title) for l in parsed.lines)
    # Si se define POP_REAL_EXPECTED_LINES, exigir ese conteo exacto; si no, usar umbral >=30
    expected = os.getenv('POP_REAL_EXPECTED_LINES')
    if expected and expected.isdigit():
        assert len(parsed.lines) == int(expected)
    else:
        assert len(parsed.lines) >= 30
    assert all(l.supplier_sku and l.supplier_sku.startswith("POP-") for l in parsed.lines)
