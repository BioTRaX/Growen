# NG-HEADER: Nombre de archivo: domain.py
# NG-HEADER: Ubicación: services/sales/domain.py
# NG-HEADER: Descripción: Reglas transaccionales compartidas de totales, cantidades, reservas y cuenta corriente.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CustomerAccountEntry, Sale, SaleLine, StockReservation


MONEY_QUANT = Decimal("0.01")
QUANTITY_QUANT = Decimal("0.01")


def money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="importe inválido") from exc


def quantity(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="cantidad inválida") from exc
    if parsed <= 0:
        raise HTTPException(status_code=422, detail="cantidad debe ser mayor a cero")
    if parsed.as_tuple().exponent < -2:
        raise HTTPException(status_code=422, detail="cantidad admite como máximo dos decimales")
    return parsed.quantize(QUANTITY_QUANT)


def additional_cost_total(costs: object) -> Decimal:
    if costs is None:
        return Decimal("0.00")
    if not isinstance(costs, list):
        raise HTTPException(status_code=422, detail="additional_costs debe ser una lista")
    total = Decimal("0")
    for index, item in enumerate(costs):
        if not isinstance(item, dict) or not str(item.get("concept") or "").strip():
            raise HTTPException(status_code=422, detail=f"additional_costs[{index}].concept es obligatorio")
        amount = money(item.get("amount"))
        if amount <= 0:
            raise HTTPException(status_code=422, detail=f"additional_costs[{index}].amount debe ser mayor a cero")
        total += amount
    return money(total)


def recalculate_sale_totals(sale: Sale, lines: list[SaleLine]) -> dict:
    subtotal = Decimal("0")
    for line in lines:
        unit = money(line.unit_price)
        qty = Decimal(str(line.qty or 0)).quantize(QUANTITY_QUANT)
        discount = money(line.line_discount)
        line_subtotal = money(unit * qty)
        line_total = money(line_subtotal * (Decimal("1") - discount / Decimal("100")))
        line.subtotal = line_subtotal
        line.tax = Decimal("0.00")
        line.total = line_total
        subtotal += line_total

    subtotal = money(subtotal)
    discount_percent = money(getattr(sale, "discount_percent", 0))
    discount_amount = money(getattr(sale, "discount_amount", 0))
    if discount_amount and discount_percent:
        discount_percent = Decimal("0.00")
    if discount_percent:
        discount_amount = money(subtotal * discount_percent / Decimal("100"))
        sale.discount_amount = discount_amount
    discount_amount = min(discount_amount, subtotal)
    costs = additional_cost_total(getattr(sale, "additional_costs", None))
    tax = money(getattr(sale, "tax", 0))
    total = money(max(subtotal - discount_amount, Decimal("0")) + costs + tax)

    sale.subtotal = subtotal
    sale.additional_cost_total = costs
    sale.total_amount = total
    paid = money(sale.paid_total)
    sale.payment_status = "PENDIENTE" if paid == 0 else ("PARCIAL" if paid < total else "PAGADA")
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "additional_cost_total": costs,
        "tax": tax,
        "total_amount": total,
    }


async def expire_reservations(db: AsyncSession, sale_id: int | None = None) -> int:
    now = datetime.utcnow()
    conditions = [StockReservation.status == "ACTIVE", StockReservation.expires_at <= now]
    if sale_id is not None:
        conditions.append(StockReservation.sale_id == sale_id)
    result = await db.execute(
        update(StockReservation)
        .where(*conditions)
        .values(status="EXPIRED", released_at=now)
    )
    return int(result.rowcount or 0)


def reservation_expiry() -> datetime:
    raw = os.getenv("SALES_RESERVATION_TTL_MINUTES", "1440")
    try:
        minutes = min(10080, max(15, int(raw)))
    except ValueError:
        minutes = 1440
    return datetime.utcnow() + timedelta(minutes=minutes)


async def account_balance(db: AsyncSession, customer_id: int) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(CustomerAccountEntry.amount), 0)).where(
            CustomerAccountEntry.customer_id == customer_id
        )
    )
    return money(value)


async def add_account_entry(
    db: AsyncSession,
    *,
    customer_id: int | None,
    entry_type: str,
    amount: Decimal,
    source_type: str,
    source_id: int,
    user_id: int | None = None,
    correlation_id: str | None = None,
    note: str | None = None,
) -> CustomerAccountEntry | None:
    if customer_id is None:
        return None
    existing = await db.scalar(
        select(CustomerAccountEntry).where(
            CustomerAccountEntry.source_type == source_type,
            CustomerAccountEntry.source_id == source_id,
            CustomerAccountEntry.entry_type == entry_type,
        )
    )
    if existing:
        return existing
    entry = CustomerAccountEntry(
        customer_id=customer_id,
        entry_type=entry_type,
        amount=money(amount),
        source_type=source_type,
        source_id=source_id,
        note=note,
        created_by=user_id,
        correlation_id=correlation_id,
    )
    db.add(entry)
    return entry
