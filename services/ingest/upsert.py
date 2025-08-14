"""Inserta o actualiza productos y variantes."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Inventory,
    Product,
    Variant,
    Supplier,
    SupplierFile,
    SupplierPriceHistory,
    SupplierProduct,
)


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


async def upsert_supplier_rows(
    rows: Iterable[dict[str, Any]],
    session: AsyncSession,
    supplier_slug: str,
    dry_run: bool = True,
) -> dict[str, int]:
    """Upsert específico para proveedores con historial de precios."""
    created = 0
    updated = 0
    supplier = await session.scalar(select(Supplier).where(Supplier.slug == supplier_slug))
    if not supplier:
        supplier = Supplier(slug=supplier_slug, name="Santa Planta")
        session.add(supplier)
        await session.flush()
    rows_list = list(rows)
    file_rec = SupplierFile(
        supplier_id=supplier.id,
        filename="upload.xlsx",
        sha256="",
        rows=len(rows_list),
        processed=not dry_run,
        dry_run=dry_run,
    )
    session.add(file_rec)
    await session.flush()
    for row in rows_list:
        spid = str(row.get("supplier_product_id"))
        sku = row.get("sku") or "SP-" + hashlib.sha1(spid.encode()).hexdigest()[:8].upper()
        title = row.get("title", "")
        purchase_price = row.get("purchase_price")
        sale_price = row.get("sale_price")
        stmt = select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier.id,
            SupplierProduct.supplier_product_id == spid,
        )
        sup_prod = await session.scalar(stmt)
        if not sup_prod:
            sup_prod = SupplierProduct(
                supplier_id=supplier.id,
                supplier_product_id=spid,
                title=title,
            )
            session.add(sup_prod)
            await session.flush()
            created += 1
        else:
            sup_prod.title = title
            updated += 1
        sup_prod.category_level_1 = row.get("category_level_1")
        sup_prod.category_level_2 = row.get("category_level_2")
        sup_prod.category_level_3 = row.get("category_level_3")
        sup_prod.min_purchase_qty = row.get("min_purchase_qty")
        last_purchase = sup_prod.current_purchase_price
        last_sale = sup_prod.current_sale_price
        sup_prod.current_purchase_price = purchase_price
        sup_prod.current_sale_price = sale_price
        sup_prod.last_seen_at = datetime.utcnow()

        delta_purchase = None
        delta_sale = None
        if last_purchase is not None and purchase_price not in (None, 0):
            if last_purchase != 0:
                delta_purchase = (purchase_price - last_purchase) / last_purchase * 100
        if last_sale is not None and sale_price not in (None, 0):
            if last_sale != 0:
                delta_sale = (sale_price - last_sale) / last_sale * 100
        session.add(
            SupplierPriceHistory(
                supplier_product_fk=sup_prod.id,
                file_fk=file_rec.id,
                as_of_date=date.today(),
                purchase_price=purchase_price,
                sale_price=sale_price,
                delta_purchase_pct=delta_purchase,
                delta_sale_pct=delta_sale,
            )
        )

        # producto interno
        stmt = select(Variant).where(Variant.sku == sku)
        variant = await session.scalar(stmt)
        if not variant:
            product = Product(sku_root=sku, title=title, status="draft")
            session.add(product)
            await session.flush()
            variant = Variant(product_id=product.id, sku=sku, price=sale_price)
            session.add(variant)
            await session.flush()
            inventory = Inventory(
                variant_id=variant.id,
                stock_qty=0,
                min_qty=row.get("min_qty", 0),
                warehouse="central",
            )
            session.add(inventory)
        else:
            if sale_price is not None:
                variant.price = sale_price
        sup_prod.internal_product_id = variant.product_id
        sup_prod.internal_variant_id = variant.id

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return {"created": created, "updated": updated}
