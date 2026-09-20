#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_santaplanta_text_contract.py
# NG-HEADER: Ubicación: tests/test_santaplanta_text_contract.py
# NG-HEADER: Descripción: Contrato textual del remito 0001-00099596 de Santa Planta.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from datetime import datetime
from decimal import Decimal

from services.importers.santaplanta_pipeline import (
    _extract_expected_counts_and_totals,
    _parse_santa_planta_text_rows,
    _parse_header_text,
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


TEXT_2026 = """SANTA PLANTA S.R.L. Documento No Válido Como Factura REMITO
Distribuidora de Grow Shops Nº 0007-00019286
R Fecha de emisión 8/9/2026
Av. Amancio Alcorta 2184
(1283) C.A.B.A. - www.SantaPlanta.com.ar Tel.: C.U.I.T.: 30-71582721-9
Código Producto/Servicio Cantidad % Bonif. P.Unitario C/IVA Total
000000043 Green leaf acaros y orugas 100ml 1,00 0,00 2.772,00 2.772,00
000000046 Unidad Fumanchu celulosa 1 1/4 5,00 0,00 532,00 2.660,00
023503823 Pot floracion 100ml sen:19102 (pack x 24u -15%) 1,00 0,00 3.610,04 3.610,04
023503849 Pot vege 100ml sen:19100 (pack x 24u -15%) 1,00 0,00 3.498,96 3.498,96
Cantidad de items: Importe Total 12.541,00
"""


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


def test_contract_2026_extracts_header_and_rows():
    events = []
    remito, fecha = _parse_header_text(TEXT_2026, events)
    assert remito == "0007-00019286"
    assert fecha == datetime(2026, 9, 8)

    lines = _parse_santa_planta_text_rows(TEXT_2026, events)
    assert len(lines) == 4
    assert lines[0].supplier_sku == "000000043"
    assert lines[0].qty == Decimal("1.00")
    assert lines[0].unit_cost_bonif == Decimal("2772.00")
    assert lines[0].total == Decimal("2772.00")
    assert lines[2].supplier_sku == "023503823"
    assert lines[2].unit_cost_bonif == Decimal("3610.04")
    assert lines[3].supplier_sku == "023503849"
    assert lines[3].unit_cost_bonif == Decimal("3498.96")
    assert sum(line.total for line in lines) == Decimal("12541.00")

