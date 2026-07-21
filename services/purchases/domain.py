#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: domain.py
# NG-HEADER: Ubicación: services/purchases/domain.py
# NG-HEADER: Descripción: Reglas transaccionales y monetarias del dominio de compras.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Reglas reutilizables del dominio de compras."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, Purchase, PurchaseLine, SupplierProduct


MONEY_QUANT = Decimal("0.01")


def as_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def line_amounts(line: PurchaseLine, purchase: Purchase) -> dict[str, Decimal]:
    gross = as_decimal(line.unit_cost)
    discount = as_decimal(line.line_discount)
    vat_rate = as_decimal(line.line_vat_rate if line.line_vat_rate is not None else purchase.vat_rate)
    quantity = as_decimal(line.qty)
    net_unit = (gross * (Decimal("1") - discount / Decimal("100"))).quantize(MONEY_QUANT)
    subtotal = (net_unit * quantity).quantize(MONEY_QUANT)
    tax = (subtotal * vat_rate / Decimal("100")).quantize(MONEY_QUANT)
    return {
        "gross_unit": gross.quantize(MONEY_QUANT),
        "net_unit": net_unit,
        "subtotal": subtotal,
        "tax": tax,
        "total": (subtotal + tax).quantize(MONEY_QUANT),
    }


def purchase_amounts(purchase: Purchase) -> dict[str, Decimal]:
    subtotal = sum((line_amounts(line, purchase)["subtotal"] for line in purchase.lines), Decimal("0"))
    discount = as_decimal(purchase.global_discount)
    discounted = (subtotal * (Decimal("1") - discount / Decimal("100"))).quantize(MONEY_QUANT)
    tax = sum((line_amounts(line, purchase)["tax"] for line in purchase.lines), Decimal("0"))
    return {"subtotal": subtotal.quantize(MONEY_QUANT), "tax": tax, "total": (discounted + tax).quantize(MONEY_QUANT)}


def validate_line_minimum(line: PurchaseLine) -> list[str]:
    errors: list[str] = []
    quantity = as_decimal(line.qty)
    if quantity <= 0 or quantity != quantity.to_integral_value():
        errors.append("La cantidad debe ser un entero positivo")
    if as_decimal(line.unit_cost) <= 0:
        errors.append("El costo de compra debe ser positivo")
    if not (line.title or "").strip():
        errors.append("El nombre del proveedor es obligatorio")
    discount = as_decimal(line.line_discount)
    if discount < 0 or discount > 100:
        errors.append("La bonificación debe estar entre 0 y 100")
    return errors


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:180] or "producto"


def _sku_root(title: str, line_id: int) -> str:
    prefix = "".join(ch for ch in title.upper() if ch.isalnum())[:8] or "PRD"
    return f"{prefix}{line_id}"[:50]


async def ensure_product_for_line(
    db: AsyncSession,
    purchase: Purchase,
    line: PurchaseLine,
) -> tuple[Product, SupplierProduct | None, bool]:
    """Resuelve por SKU exacto o crea producto/oferta sin canonizar."""
    sku = (line.supplier_sku or "").strip()
    supplier_item: SupplierProduct | None = None
    if sku:
        supplier_item = await db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == purchase.supplier_id,
                SupplierProduct.supplier_product_id == sku,
            )
        )
        if supplier_item and supplier_item.internal_product_id:
            product = await db.get(Product, supplier_item.internal_product_id)
            if product:
                line.supplier_item_id = supplier_item.id
                line.product_id = product.id
                return product, supplier_item, False

    product = Product(
        sku_root=_sku_root(line.title, line.id),
        title=line.title.strip(),
        slug=f"{_slug(line.title)}-{purchase.id}-{line.id}",
        status="active",
        stock=0,
    )
    db.add(product)
    await db.flush()

    if sku:
        if supplier_item:
            supplier_item.internal_product_id = product.id
            supplier_item.title = line.title[:200]
        else:
            supplier_item = SupplierProduct(
                supplier_id=purchase.supplier_id,
                supplier_product_id=sku,
                title=line.title[:200],
                internal_product_id=product.id,
            )
            db.add(supplier_item)
            await db.flush()
        line.supplier_item_id = supplier_item.id
    line.product_id = product.id
    line.state = "OK"
    return product, supplier_item, True
