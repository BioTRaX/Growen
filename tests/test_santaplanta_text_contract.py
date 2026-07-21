#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_santaplanta_text_contract.py
# NG-HEADER: Ubicación: tests/test_santaplanta_text_contract.py
# NG-HEADER: Descripción: Contrato textual del remito 0001-00099596 de Santa Planta.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from decimal import Decimal

from services.importers.santaplanta_pipeline import (
    _extract_expected_counts_and_totals,
    _parse_santa_planta_text_rows,
)


TEXT = """Código Producto/Servicio Cant. P. Unitario Bonif. Bonifcado Subtotal IVA C/IVA Total
6584 *LA POTA PERLITA (5 DM) 2 2.059,20 0,00 2.059,20 4.118,40 0,00 2.059,20 4.118,40
3502 *MACETA SOPLADA (PACK X 100 U -20% 100 193,80 20,00 155,04 15.504,00 0,00 155,04 15.504,00
DESC) (1 LT)
564 *MACETA SOPLADA (PACK X 100 U -20% 100 660,45 20,00 528,36 52.836,00 0,00 528,36 52.836,00
DESC) (10 LT)
468 *MACETA SOPLADA (PACK X 100 U -20% 20 1.514,70 20,00 1.211,76 24.235,20 0,00 1.211,76 24.235,20
DESC) (20 LT)
873 *MACETA SOPLADA (PACK X 100 U -20% 100 385,05 20,00 308,04 30.804,00 0,00 308,04 30.804,00
DESC) (5 LT)
318 *VAMP GALLINA FLORA (PACK X 10 U 2 2.216,80 0,00 2.216,80 4.433,60 0,00 2.216,80 4.433,60
-20% DESC)
545 *VAMP GALLINA VEGE (PACK X 10 U -20% 2 2.216,80 0,00 2.216,80 4.433,60 0,00 2.216,80 4.433,60
DESC)
5630 *VAMP HUMUSKASHI 2 3.146,00 0,00 3.146,00 6.292,00 0,00 3.146,00 6.292,00
118 *VAMP MURCIELAGO FLORA (PACK X 10 U 2 3.168,80 0,00 3.168,80 6.337,60 0,00 3.168,80 6.337,60
-20% DESC)
119 *VAMP MURCIELAGO VEGETATIVO (PACK 2 3.168,80 0,00 3.168,80 6.337,60 0,00 3.168,80 6.337,60
X 10 U -20% DESC)
Cantidad De Items: 10 Importe Total: $ 155,332.00"""


def test_contract_extracts_ten_lines_and_exact_total():
    events = []
    lines = _parse_santa_planta_text_rows(TEXT, events)
    footer = _extract_expected_counts_and_totals(TEXT)
    assert len(lines) == footer["expected_items"] == 10
    assert footer["importe_total"] == Decimal("155332.00")
    assert sum(line.total or Decimal("0") for line in lines) == Decimal("155332.00")
    assert lines[1].supplier_sku == "3502"
    assert lines[1].qty == Decimal("100")
    assert lines[1].pct_bonif == Decimal("20.00")
    assert lines[1].unit_cost_bonif == Decimal("155.04")
    assert "DESC) (1 LT)" in lines[1].title
    assert "-20% DESC" in lines[5].title
    assert lines[5].pct_bonif == Decimal("0.00")
