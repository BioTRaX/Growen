"""Inserta o actualiza productos y variantes."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Inventory, Product, Variant


async def upsert_rows(
    rows: Iterable[dict[str, Any]],
    session: AsyncSession,
    supplier_name: str,
    dry_run: bool = True,
) -> dict[str, int]:
    """Crea o actualiza registros en la base."""
    created = 0
    updated = 0
    for row in rows:
        sku = _generate_sku(row, supplier_name)
        title = row.get("title", "")
        price = row.get("price")
        stmt = select(Variant).where(Variant.sku == sku)
        existing = await session.scalar(stmt)
        if existing:
            if not dry_run:
                if price is not None:
                    existing.price = price
            updated += 1
            continue
        if dry_run:
            created += 1
            continue
        product = Product(sku_root=sku, title=title)
        session.add(product)
        await session.flush()
        variant = Variant(product_id=product.id, sku=sku, price=price)
        session.add(variant)
        await session.flush()
        inventory = Inventory(variant_id=variant.id, stock_qty=0, min_qty=row.get("min_qty", 0))
        session.add(inventory)
        created += 1
    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return {"created": created, "updated": updated}


def _generate_sku(row: dict[str, Any], supplier_name: str) -> str:
    sku = row.get("sku")
    if sku:
        return str(sku).strip().upper()
    barcode = row.get("barcode")
    if barcode:
        return f"EAN-{barcode}".upper()
    base = f"{supplier_name}-{row.get('title','')}-{row.get('variant_value','')}"
    return "SUP-" + hashlib.sha1(base.encode()).hexdigest()[:8].upper()
