#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_parse_remito_sample_pdf.py
# NG-HEADER: Ubicación: tests/test_parse_remito_sample_pdf.py
# NG-HEADER: Descripción: Test de parseo sobre remito de ejemplo Santa Planta
# NG-HEADER: Lineamientos: Ver AGENTS.md
from pathlib import Path
import os
import pytest

from services.importers.santaplanta_pipeline import parse_remito


@pytest.mark.skipif(not Path("Devs/Remito_00099596_RUIZ DIAZ CLAUDIO ALEJANDRO.pdf").exists(), reason="PDF de ejemplo no presente")
def test_parse_remito_example_pdf():
    pdf_path = Path("Devs/Remito_00099596_RUIZ DIAZ CLAUDIO ALEJANDRO.pdf")
    # Debug temporal: verificar que parse_remito es función y no None / objeto inesperado
    assert callable(parse_remito), f"parse_remito no es callable: {parse_remito!r}"
    res = parse_remito(pdf_path, correlation_id="test-corr", use_ocr_auto=False, force_ocr=False, debug=True)
    # Dump rápido de eventos en primera corrida para diagnóstico cuando remito_number falta
    try:
        if not res.remito_number:
            debug_path = Path("logs/first_run_remito_events.log")
            debug_path.write_text("\n".join([str(e) for e in res.events]))
    except Exception:
        pass
    # Validar que se detecta o bien remito_number 0001-00099596 o al menos fecha/número parcial.
    # Dependiendo de heurísticas puede variar. Aceptamos equivalentes sin cero padding.
    try:
        rn = (res.remito_number or "").replace(" ", "")
    except AttributeError:
        raise AssertionError(f"parse_remito devolvió None. Eventos iniciales: {res.events[:25] if res else 'res=None'}")
    assert "99596" in rn, f"Remito number parcial esperado, obtenido: {res.remito_number}. Eventos header: {[e for e in res.events if e.get('stage') in ('start','header','header_reparse')][:10]}"
    # Esperamos al menos 8 líneas (el ejemplo tiene 10). Si menos, revisar eventos para diagnóstico.
    assert len(res.lines) >= 8, f"Se esperaban >=8 líneas, got {len(res.lines)}. Eventos: {[e for e in res.events if e.get('stage') in ('pdfplumber','camelot','summary')] }"
    # Confianza clásica debería superar umbral mínimo default (0.55)
    assert getattr(res, 'classic_confidence', 0) >= 0.55, f"Confianza clásica baja: {res.classic_confidence}"
    # Chequear que al menos una línea contenga un SKU conocido del ejemplo
    skus = {l.supplier_sku for l in res.lines if l.supplier_sku}
    sample_expected = {"6584", "3502", "564", "468", "873"}
    if not (skus & sample_expected):
        # Extraer eventos diagnósticos de enforcement
        enf_events = [e for e in res.events if e.get('event','').startswith('expected_enforcement') or e.get('event','').startswith('expected_sku_enforced') or 'expected_skus_still_missing'==e.get('event')]
        # También mostrar primeros títulos y SKUs crudos
        raw_lines = [
            {
                'i': idx,
                'sku': ln.supplier_sku,
                'title': (ln.title or '')[:80]
            } for idx, ln in enumerate(res.lines[:12])
        ]
        raise AssertionError(f"No se encontraron SKUs esperados en {skus}. Eventos enforcement: {enf_events}. Primeras lineas: {raw_lines}")
    # Si pasó, todo ok
