#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: fix_canonical_sku_from_canonical_product.py
# NG-HEADER: Ubicación: scripts/fix_canonical_sku_from_canonical_product.py
# NG-HEADER: Descripción: Sincroniza canonical_sku de Product con CanonicalProduct.sku_custom
# NG-HEADER: Lineamientos: Ver AGENTS.md

import asyncio
import sys
from pathlib import Path

# FIX: Windows ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product, CanonicalProduct, ProductEquivalence, SupplierProduct
from sqlalchemy import select
from db.sku_utils import is_canonical_sku

async def fix():
    """Sincroniza canonical_sku de Product con CanonicalProduct.sku_custom cuando aplica."""
    async with SessionLocal() as db:
        print("=== Sincronizando canonical_sku desde CanonicalProduct ===\n")
        
        # Buscar todos los CanonicalProduct con sku_custom canónico
        canonical_products = await db.scalars(
            select(CanonicalProduct).where(
                CanonicalProduct.sku_custom.isnot(None)
            )
        )
        
        updated_count = 0
        skipped_count = 0
        
        for cp in canonical_products:
            if not is_canonical_sku(cp.sku_custom):
                continue
            
            # Buscar Product asociado a través de ProductEquivalence -> SupplierProduct
            eq = await db.scalar(
                select(ProductEquivalence).where(
                    ProductEquivalence.canonical_product_id == cp.id
                )
            )
            
            if not eq:
                continue
            
            sp = await db.get(SupplierProduct, eq.supplier_product_id)
            if not sp or not sp.internal_product_id:
                continue
            
            product = await db.get(Product, sp.internal_product_id)
            if not product:
                continue
            
            # Si el Product tiene un canonical_sku diferente al CanonicalProduct.sku_custom
            if product.canonical_sku != cp.sku_custom:
                print(f"Actualizando Product ID={product.id}:")
                print(f"  canonical_sku actual: '{product.canonical_sku}'")
                print(f"  canonical_sku nuevo:  '{cp.sku_custom}' (desde CanonicalProduct ID={cp.id})")
                
                # Verificar que no haya conflicto con otro producto
                existing = await db.scalar(
                    select(Product).where(
                        Product.canonical_sku == cp.sku_custom,
                        Product.id != product.id
                    )
                )
                
                if existing:
                    print(f"  ⚠ Omitido: SKU '{cp.sku_custom}' ya existe en Product ID={existing.id}")
                    skipped_count += 1
                else:
                    product.canonical_sku = cp.sku_custom
                    updated_count += 1
                    print(f"  ✓ Actualizado")
        
        if updated_count > 0:
            await db.commit()
            print(f"\n✓ {updated_count} productos actualizados")
        else:
            print(f"\n✓ No se requirieron actualizaciones")
        
        if skipped_count > 0:
            print(f"⚠ {skipped_count} productos omitidos por conflictos")

if __name__ == "__main__":
    asyncio.run(fix())

