#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_fer_0018_detailed.py
# NG-HEADER: Ubicación: scripts/check_fer_0018_detailed.py
# NG-HEADER: Descripción: Verificación detallada del producto FER_0018_ORG
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
from db.models import Product, CanonicalProduct, SupplierProduct, ProductEquivalence, Category
from sqlalchemy import select, func, or_

async def check():
    sku_search = "FER_0018_ORG"
    async with SessionLocal() as db:
        print(f"=== Búsqueda detallada de SKU: {sku_search} ===\n")
        
        # 1. Buscar en Product.canonical_sku
        print("1. Product.canonical_sku:")
        p1 = await db.scalar(select(Product).where(Product.canonical_sku == sku_search))
        if p1:
            print(f"   ✓ Encontrado: ID={p1.id}")
            print(f"      canonical_sku='{p1.canonical_sku}'")
            print(f"      sku_root='{p1.sku_root}'")
            print(f"      title='{p1.title}'")
            print(f"      category_id={p1.category_id}")
        else:
            print(f"   ✗ NO encontrado")
        
        # 2. Buscar en CanonicalProduct.sku_custom
        print("\n2. CanonicalProduct.sku_custom:")
        cp1 = await db.scalar(select(CanonicalProduct).where(CanonicalProduct.sku_custom == sku_search))
        if cp1:
            print(f"   ✓ Encontrado: ID={cp1.id}")
            print(f"      sku_custom='{cp1.sku_custom}'")
            print(f"      ng_sku='{cp1.ng_sku}'")
            print(f"      name='{cp1.name}'")
            print(f"      category_id={cp1.category_id}")
            
            # Buscar Product asociado
            eq = await db.scalar(
                select(ProductEquivalence)
                .where(ProductEquivalence.canonical_product_id == cp1.id)
            )
            if eq:
                sp = await db.get(SupplierProduct, eq.supplier_product_id)
                if sp and sp.internal_product_id:
                    p_associated = await db.get(Product, sp.internal_product_id)
                    if p_associated:
                        print(f"      → Product asociado: ID={p_associated.id}, canonical_sku='{p_associated.canonical_sku}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 3. Buscar en CanonicalProduct.ng_sku
        print("\n3. CanonicalProduct.ng_sku:")
        cp2 = await db.scalar(select(CanonicalProduct).where(CanonicalProduct.ng_sku == sku_search))
        if cp2:
            print(f"   ✓ Encontrado: ID={cp2.id}")
            print(f"      sku_custom='{cp2.sku_custom}'")
            print(f"      ng_sku='{cp2.ng_sku}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 4. Buscar productos con "Namaste" en el título
        print("\n4. Productos con 'Namaste' en título:")
        namaste = await db.scalars(
            select(Product).where(Product.title.ilike("%Namaste%"))
            .limit(5)
        )
        for p in namaste:
            print(f"   - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}', title='{p.title[:60]}'")
        
        # 5. Buscar todos los productos con categoría "Fertilizantes"
        print("\n5. Productos con categoría 'Fertilizantes':")
        fert_cat = await db.scalar(select(Category).where(func.lower(Category.name) == "fertilizantes"))
        if fert_cat:
            print(f"   Categoría encontrada: ID={fert_cat.id}, name='{fert_cat.name}'")
            fert_products = await db.scalars(
                select(Product).where(Product.category_id == fert_cat.id)
                .order_by(Product.canonical_sku)
                .limit(10)
            )
            for p in fert_products:
                print(f"   - ID={p.id}: canonical_sku='{p.canonical_sku}', title='{p.title[:50]}'")
        else:
            print(f"   ✗ Categoría 'Fertilizantes' no encontrada")
        
        # 6. Buscar en Variant.sku
        print("\n6. Variant.sku:")
        from db.models import Variant
        v = await db.scalar(select(Variant).where(Variant.sku == sku_search))
        if v:
            print(f"   ✓ Encontrado: ID={v.id}, product_id={v.product_id}")
            p_v = await db.get(Product, v.product_id)
            if p_v:
                print(f"      Product: ID={p_v.id}, canonical_sku='{p_v.canonical_sku}'")
        else:
            print(f"   ✗ NO encontrado")

if __name__ == "__main__":
    asyncio.run(check())

