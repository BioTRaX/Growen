#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_all_fer_products.py
# NG-HEADER: Ubicación: scripts/check_all_fer_products.py
# NG-HEADER: Descripción: Verifica todos los productos y SKUs generados
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
from db.models import Product, Category
from sqlalchemy import select, func

async def check():
    async with SessionLocal() as db:
        print("=== Análisis de productos y SKUs ===\n")
        
        # 1. Contar productos con y sin canonical_sku
        total = await db.scalar(select(func.count(Product.id)))
        with_canonical = await db.scalar(
            select(func.count(Product.id)).where(Product.canonical_sku.isnot(None))
        )
        without_canonical = total - with_canonical
        
        print(f"Total productos: {total}")
        print(f"Con canonical_sku: {with_canonical}")
        print(f"Sin canonical_sku: {without_canonical}\n")
        
        # 2. Listar algunos productos con canonical_sku
        print("=== Primeros 20 productos con canonical_sku ===")
        products = await db.scalars(
            select(Product).where(Product.canonical_sku.isnot(None))
            .order_by(Product.canonical_sku)
            .limit(20)
        )
        for p in products:
            cat_name = "N/A"
            if p.category_id:
                cat = await db.get(Category, p.category_id)
                if cat:
                    cat_name = cat.name
            print(f"ID={p.id:3d} | canonical_sku='{p.canonical_sku:15s}' | sku_root='{p.sku_root:15s}' | cat='{cat_name}' | title='{p.title[:40]}'")
        
        # 3. Buscar productos con categoría "Fertilizante" o similar
        print("\n=== Productos con categoría relacionada a Fertilizante ===")
        fert_cats = await db.scalars(
            select(Category).where(
                func.lower(Category.name).like("%fertilizante%")
            )
        )
        fert_cat_list = list(fert_cats)
        if fert_cat_list:
            for cat in fert_cat_list:
                print(f"\nCategoría: {cat.name} (ID={cat.id})")
                cat_products = await db.scalars(
                    select(Product).where(Product.category_id == cat.id)
                    .limit(10)
                )
                for p in cat_products:
                    print(f"  - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}', title='{p.title[:50]}'")
        else:
            print("No se encontraron categorías con 'fertilizante'")
        
        # 4. Verificar secuencias de SKU
        print("\n=== Secuencias de SKU ===")
        try:
            sequences = await db.execute(
                select(func.text("category_code"), func.text("next_seq"))
                .select_from(func.text("sku_sequences"))
            )
            # En PostgreSQL necesitamos usar text() diferente
            from sqlalchemy import text
            seq_rows = await db.execute(text("SELECT category_code, next_seq FROM sku_sequences ORDER BY category_code"))
            for row in seq_rows:
                print(f"  {row[0]}: next_seq={row[1]}")
        except Exception as e:
            print(f"  Error al leer secuencias: {e}")

if __name__ == "__main__":
    asyncio.run(check())

