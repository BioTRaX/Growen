#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sales_v4_domain.py
# NG-HEADER: Ubicación: tests/test_sales_v4_domain.py
# NG-HEADER: Descripción: Pruebas de precisión, costos adicionales y contratos comerciales de Ventas Fase 4.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services.sales.domain import quantity, recalculate_sale_totals
from services.sales.schemas import SaleQuoteRequest


class DummySale:
    discount_percent = Decimal("10")
    discount_amount = Decimal("0")
    additional_costs = [{"concept": "Envío", "amount": "12.35"}]
    additional_cost_total = Decimal("0")
    tax = Decimal("5.10")
    subtotal = Decimal("0")
    total_amount = Decimal("0")
    paid_total = Decimal("0")
    payment_status = None


class DummyLine:
    qty = Decimal("1.25")
    unit_price = Decimal("100")
    line_discount = Decimal("20")
    subtotal = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")


def test_total_autoritativo_incluye_costos_adicionales_e_impuestos():
    sale = DummySale()
    result = recalculate_sale_totals(sale, [DummyLine()])

    assert result == {
        "subtotal": Decimal("100.00"),
        "discount_amount": Decimal("10.00"),
        "additional_cost_total": Decimal("12.35"),
        "tax": Decimal("5.10"),
        "total_amount": Decimal("107.45"),
    }
    assert sale.total_amount == Decimal("107.45")


def test_cantidad_acepta_dos_decimales_y_rechaza_precision_excesiva():
    assert quantity("2.50") == Decimal("2.50")
    with pytest.raises(HTTPException, match="máximo dos decimales"):
        quantity("2.501")


def test_schema_quote_rechaza_cantidad_con_tres_decimales():
    with pytest.raises(ValidationError):
        SaleQuoteRequest.model_validate({"items": [{"product_id": 1, "qty": "1.001"}]})
