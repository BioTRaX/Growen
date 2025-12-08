#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_sku_fer_0018.py
# NG-HEADER: Ubicación: scripts/check_sku_fer_0018.py
# NG-HEADER: Descripción: Script temporal para verificar SKU FER_0018_ORG
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
from db.models import Product
from sqlalchemy import select, func, or_

async def check():
    sku_search = "FER_0018_ORG"
    async with SessionLocal() as db:
        print(f"=== Búsqueda de SKU: {sku_search} ===\n")
        
        # 1. Búsqueda exacta por canonical_sku
        print("1. Búsqueda exacta por canonical_sku:")
        p1 = await db.scalar(select(Product).where(Product.canonical_sku == sku_search))
        if p1:
            print(f"   ✓ Encontrado: ID={p1.id}, canonical_sku='{p1.canonical_sku}', sku_root='{p1.sku_root}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 2. Búsqueda exacta por sku_root
        print("\n2. Búsqueda exacta por sku_root:")
        p2 = await db.scalar(select(Product).where(Product.sku_root == sku_search))
        if p2:
            print(f"   ✓ Encontrado: ID={p2.id}, canonical_sku='{p2.canonical_sku}', sku_root='{p2.sku_root}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 3. Búsqueda case-insensitive canonical_sku
        print("\n3. Búsqueda case-insensitive canonical_sku:")
        p3 = await db.scalar(
            select(Product).where(
                func.lower(Product.canonical_sku) == sku_search.lower()
            )
        )
        if p3:
            print(f"   ✓ Encontrado: ID={p3.id}, canonical_sku='{p3.canonical_sku}', sku_root='{p3.sku_root}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 4. Búsqueda case-insensitive sku_root
        print("\n4. Búsqueda case-insensitive sku_root:")
        p4 = await db.scalar(
            select(Product).where(
                func.lower(Product.sku_root) == sku_search.lower()
            )
        )
        if p4:
            print(f"   ✓ Encontrado: ID={p4.id}, canonical_sku='{p4.canonical_sku}', sku_root='{p4.sku_root}'")
        else:
            print(f"   ✗ NO encontrado")
        
        # 5. Búsqueda por prefijo (similar)
        print("\n5. Búsqueda por prefijo 'FER_0018':")
        similar = await db.scalars(
            select(Product).where(
                or_(
                    Product.canonical_sku.like("FER_0018%"),
                    Product.sku_root.like("FER_0018%")
                )
            ).limit(10)
        )
        similar_list = list(similar)
        if similar_list:
            print(f"   Encontrados {len(similar_list)} productos similares:")
            for p in similar_list:
                print(f"     - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}'")
        else:
            print(f"   ✗ NO encontrados productos similares")
        
        # 6. Listar todos los productos con canonical_sku que empiecen con FER
        print("\n6. Todos los productos con canonical_sku que empiezan con 'FER':")
        fer_products = await db.scalars(
            select(Product).where(
                Product.canonical_sku.like("FER%")
            ).order_by(Product.canonical_sku).limit(20)
        )
        fer_list = list(fer_products)
        if fer_list:
            print(f"   Encontrados {len(fer_list)} productos:")
            for p in fer_list:
                print(f"     - ID={p.id}: canonical_sku='{p.canonical_sku}', sku_root='{p.sku_root}'")
        else:
            print(f"   ✗ NO encontrados productos con prefijo FER")

if __name__ == "__main__":
    asyncio.run(check())

