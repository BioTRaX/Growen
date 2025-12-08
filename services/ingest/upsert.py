# NG-HEADER: Nombre de archivo: upsert.py
# NG-HEADER: Ubicación: services/ingest/upsert.py
# NG-HEADER: Descripción: Realiza upserts de productos durante la ingesta.
# NG-HEADER: Lineamientos: Ver AGENTS.md
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
from db.sku_utils import is_canonical_sku


async def upsert_rows(
    rows: Iterable[dict[str, Any]],
    session: AsyncSession,
    supplier_name: str,
    dry_run: bool = True,
) -> dict[str, int]:
    """Crea o actualiza registros en la base.
    
    NOTA: Esta función está deprecada para uso con SKUs no canónicos.
    Para productos nuevos, usar endpoints que generen SKUs canónicos (XXX_####_YYY).
    """
    created = 0
    updated = 0
    for row in rows:
        sku = await _generate_sku_async(row, supplier_name, session)
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
        # Intentar usar canonical_sku si el SKU es canónico
        canonical_sku = sku if is_canonical_sku(sku) else None
        product = Product(sku_root=sku, title=title)
        if canonical_sku:
            product.canonical_sku = canonical_sku
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


async def _generate_sku_async(
    row: dict[str, Any], 
    supplier_name: str, 
    session: AsyncSession
) -> str:
    """Genera SKU canónico cuando sea posible, o valida SKU existente.
    
    Prioridad:
    1. Si viene `sku` en el row: validar que sea canónico (XXX_####_YYY)
    2. Si viene `category_name`: generar SKU canónico automáticamente
    3. Si no hay categoría ni SKU válido: lanzar error (requiere migración)
    
    NOTA: Los SKUs no canónicos (EAN-xxx, SUP-xxx) están deprecados.
    """
    sku = row.get("sku")
    if sku:
        sku_clean = str(sku).strip().upper()
        # Si ya es canónico, usarlo directamente
        if is_canonical_sku(sku_clean):
            return sku_clean
        # Si no es canónico pero tiene formato legacy, intentar generar canónico
        # si hay categoría disponible
        category_name = row.get("category_name") or row.get("category_level_1")
        if category_name:
            from db.sku_generator import generate_canonical_sku
            subcategory_name = row.get("subcategory_name") or row.get("category_level_2")
            try:
                return await generate_canonical_sku(session, category_name, subcategory_name or category_name)
            except Exception:
                # Si falla la generación, usar el SKU original (compatibilidad temporal)
                pass
        # Si no hay categoría, rechazar SKU no canónico
        raise ValueError(
            f"SKU no canónico '{sku_clean}' requiere categoría para generar formato canónico. "
            f"Formato esperado: XXX_####_YYY (ej: FLO_0001_FER)"
        )
    
    # Si no viene SKU, intentar generar desde categoría
    category_name = row.get("category_name") or row.get("category_level_1")
    if category_name:
        from db.sku_generator import generate_canonical_sku
        subcategory_name = row.get("subcategory_name") or row.get("category_level_2")
        return await generate_canonical_sku(session, category_name, subcategory_name or category_name)
    
    # Fallback: error (no se generan más SKUs no canónicos)
    raise ValueError(
        f"No se puede generar SKU: falta 'sku' canónico o 'category_name'. "
        f"Formato requerido: XXX_####_YYY (ej: FLO_0001_FER)"
    )


def _generate_sku(row: dict[str, Any], supplier_name: str) -> str:
    """DEPRECADO: Usar _generate_sku_async en su lugar.
    
    Esta función genera SKUs no canónicos y está deprecada.
    Mantenida solo para compatibilidad temporal.
    """
    sku = row.get("sku")
    if sku:
        sku_clean = str(sku).strip().upper()
        if is_canonical_sku(sku_clean):
            return sku_clean
        # Si no es canónico, retornar tal cual (compatibilidad temporal)
        return sku_clean
    barcode = row.get("barcode")
    if barcode:
        # DEPRECADO: EAN-xxx no es formato canónico
        return f"EAN-{barcode}".upper()
    # DEPRECADO: SUP-xxx no es formato canónico
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
        # Intentar generar SKU canónico si hay categoría
        sku = None
        if row.get("sku"):
            sku_clean = str(row.get("sku")).strip().upper()
            if is_canonical_sku(sku_clean):
                sku = sku_clean
        if not sku:
            category_name = row.get("category_name") or row.get("category_level_1")
            if category_name:
                from db.sku_generator import generate_canonical_sku
                subcategory_name = row.get("subcategory_name") or row.get("category_level_2")
                try:
                    sku = await generate_canonical_sku(session, category_name, subcategory_name or category_name)
                except Exception:
                    pass
        # Fallback temporal: usar supplier_product_id como SKU de proveedor (no canónico)
        # NOTA: supplier_product_id es el SKU del proveedor, no el SKU interno canónico
        if not sku:
            # DEPRECADO: Este formato no es canónico, pero se mantiene para compatibilidad
            sku = "SP-" + hashlib.sha1(spid.encode()).hexdigest()[:8].upper()
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
        # Buscar por canonical_sku primero si el SKU es canónico
        variant = None
        if is_canonical_sku(sku):
            # Buscar producto por canonical_sku
            product_by_canonical = await session.scalar(
                select(Product).where(Product.canonical_sku == sku)
            )
            if product_by_canonical:
                # Buscar variant asociado
                variant = await session.scalar(
                    select(Variant).where(Variant.product_id == product_by_canonical.id).limit(1)
                )
        # Si no se encontró por canonical_sku, buscar por Variant.sku
        if not variant:
            stmt = select(Variant).where(Variant.sku == sku)
            variant = await session.scalar(stmt)
        if not variant:
            # Crear producto con canonical_sku si aplica
            canonical_sku = sku if is_canonical_sku(sku) else None
            product = Product(sku_root=sku, title=title, status="draft")
            if canonical_sku:
                product.canonical_sku = canonical_sku
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
