#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_purchase_domain.py
# NG-HEADER: Ubicación: tests/test_purchase_domain.py
# NG-HEADER: Descripción: Pruebas unitarias de importes y validaciones del dominio de compras.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from datetime import date
from decimal import Decimal

from db.models import Purchase, PurchaseLine
from services.purchases.domain import line_amounts, purchase_amounts, validate_line_minimum


def _purchase_with_line(**overrides):
    purchase = Purchase(supplier_id=1, remito_number="0001-00099596", remito_date=date(2025, 8, 5), vat_rate=0)
    values = {"title": "Maceta Pack X 100 U -20% Desc", "qty": 100, "unit_cost": Decimal("193.80"), "line_discount": Decimal("20")}
    values.update(overrides)
    line = PurchaseLine(**values)
    purchase.lines = [line]
    return purchase, line


def test_line_amounts_preserve_gross_discount_and_net():
    purchase, line = _purchase_with_line()
    amounts = line_amounts(line, purchase)
    assert amounts["gross_unit"] == Decimal("193.80")
    assert amounts["net_unit"] == Decimal("155.04")
    assert amounts["subtotal"] == Decimal("15504.00")
    assert purchase_amounts(purchase)["total"] == Decimal("15504.00")


def test_minimum_rejects_fractional_negative_and_zero_values():
    _, fractional = _purchase_with_line(qty=Decimal("1.5"))
    assert any("entero positivo" in message for message in validate_line_minimum(fractional))
    _, zero_cost = _purchase_with_line(unit_cost=0)
    assert any("costo" in message.lower() for message in validate_line_minimum(zero_cost))
    _, invalid_discount = _purchase_with_line(line_discount=101)
    assert any("bonificación" in message.lower() for message in validate_line_minimum(invalid_discount))
