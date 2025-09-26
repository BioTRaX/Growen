# NG-HEADER: Nombre de archivo: test_recalc_totals.py
# NG-HEADER: Ubicación: tests/test_recalc_totals.py
# NG-HEADER: Descripción: Tests unitarios para función _recalc_totals de ventas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import pytest
from decimal import Decimal

from db.models import Sale, SaleLine
from services.routers.sales import _recalc_totals

class DummySale:
    def __init__(self, discount_percent=0, discount_amount=0, paid_total=0):
        self.discount_percent = Decimal(str(discount_percent))
        self.discount_amount = Decimal(str(discount_amount))
        self.subtotal = Decimal('0')
        self.tax = Decimal('0')
        self.total_amount = Decimal('0')
        self.paid_total = Decimal(str(paid_total))
        self.payment_status = None

class DummyLine:
    def __init__(self, qty, unit_price, line_discount=0):
        self.qty = Decimal(str(qty))
        self.unit_price = Decimal(str(unit_price))
        self.line_discount = Decimal(str(line_discount))


def test_recalc_totals_percent_discount():
    sale = DummySale(discount_percent=10)
    lines = [DummyLine(2, 100), DummyLine(1, 50, 20)]  # line1=200, line2=50*(1-0.2)=40 => subtotal=240
    _recalc_totals(sale, lines)  # 10% => discount_amount=24 => total=216
    assert sale.subtotal == Decimal('240')
    assert sale.discount_amount == Decimal('24.00')
    assert sale.total_amount == Decimal('216.00')
    assert sale.payment_status == 'PENDIENTE'


def test_recalc_totals_amount_priority():
    sale = DummySale(discount_percent=15, discount_amount=30)  # amount debe priorizar y percent ignorado
    lines = [DummyLine(3, 80)]  # subtotal=240
    _recalc_totals(sale, lines)
    assert sale.subtotal == Decimal('240')
    assert sale.discount_amount == Decimal('30')
    assert sale.total_amount == Decimal('210.00')


def test_recalc_totals_paid_partial_and_paid_full():
    # parcial
    sale = DummySale(discount_percent=0, paid_total=50)
    lines = [DummyLine(2, 60)]  # subtotal=120
    _recalc_totals(sale, lines)
    assert sale.total_amount == Decimal('120.00')
    assert sale.payment_status == 'PARCIAL'
    # pago completo
    sale2 = DummySale(discount_percent=0, paid_total=120)
    _recalc_totals(sale2, lines)
    assert sale2.payment_status == 'PAGADA'


def test_recalc_totals_negative_guard():
    # Si descuento supera subtotal, total no debe ser negativo
    sale = DummySale(discount_amount=500)
    lines = [DummyLine(2, 100)]  # subtotal=200
    _recalc_totals(sale, lines)
    assert sale.total_amount == Decimal('0')

