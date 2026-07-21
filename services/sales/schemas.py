# NG-HEADER: Nombre de archivo: schemas.py
# NG-HEADER: Ubicación: services/sales/schemas.py
# NG-HEADER: Descripción: Contratos Pydantic para cotización, reservas y cuenta corriente.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AdditionalCostInput(BaseModel):
    concept: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0)

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("amount admite como máximo dos decimales")
        return value


class SaleLineInput(BaseModel):
    product_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)
    line_discount: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @field_validator("qty")
    @classmethod
    def validate_qty_precision(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("qty admite como máximo dos decimales")
        return value


class SaleQuoteRequest(BaseModel):
    items: list[SaleLineInput]
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    additional_costs: list[AdditionalCostInput] = Field(default_factory=list)


class AccountAdjustmentInput(BaseModel):
    kind: Literal["debit", "credit"]
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)


class ReservationResponse(BaseModel):
    sale_id: int
    status: str
    expires_at: datetime | None = None
    lines: int = 0
