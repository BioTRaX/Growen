#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_product_19_sku.py
# NG-HEADER: Ubicación: scripts/check_product_19_sku.py
# NG-HEADER: Descripción: Verifica el SKU del producto 19 y búsquedas relacionadas.
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
    async with SessionLocal() as db:
        # Verificar producto 19
        p = await db.get(Product, 19)
        if p:
            print(f"=== Producto ID 19 ===")
            print(f"canonical_sku: {repr(p.canonical_sku)}")
            print(f"sku_root: {repr(p.sku_root)}")
            print(f"title: {p.title}")
            print()
        else:
            print("Producto 19: NO ENCONTRADO")
            return
        
        # Buscar por SKU que debería funcionar
        sku = "FER_0015_TOP"
        print(f"=== Búsquedas para SKU '{sku}' ===")
        
        # Búsqueda 1: canonical_sku exacto
        p1 = await db.scalar(select(Product).where(Product.canonical_sku == sku))
        print(f"1. Product.canonical_sku == '{sku}': {p1.id if p1 else 'NO ENCONTRADO'}")
        
        # Búsqueda 2: sku_root
        p2 = await db.scalar(select(Product).where(Product.sku_root == sku))
        print(f"2. Product.sku_root == '{sku}': {p2.id if p2 else 'NO ENCONTRADO'}")
        
        # Búsqueda 3: case-insensitive canonical_sku
        p3 = await db.scalar(
            select(Product).where(func.lower(Product.canonical_sku) == sku.lower())
        )
        print(f"3. Product.canonical_sku (case-insensitive) == '{sku}': {p3.id if p3 else 'NO ENCONTRADO'}")
        
        # Búsqueda 4: case-insensitive sku_root
        p4 = await db.scalar(
            select(Product).where(func.lower(Product.sku_root) == sku.lower())
        )
        print(f"4. Product.sku_root (case-insensitive) == '{sku}': {p4.id if p4 else 'NO ENCONTRADO'}")
        
        # Ver todos los SKUs del producto 19
        print()
        print(f"=== SKUs del producto 19 ===")
        print(f"canonical_sku (repr): {repr(p.canonical_sku)}")
        print(f"canonical_sku (str): {str(p.canonical_sku)}")
        print(f"canonical_sku (len): {len(p.canonical_sku) if p.canonical_sku else 0}")
        print(f"sku_root (repr): {repr(p.sku_root)}")
        print(f"sku_root (str): {str(p.sku_root)}")
        print(f"sku_root (len): {len(p.sku_root) if p.sku_root else 0}")
        
        # Comparación directa
        print()
        print(f"=== Comparaciones ===")
        print(f"p.canonical_sku == '{sku}': {p.canonical_sku == sku}")
        print(f"p.canonical_sku == '{sku.lower()}': {p.canonical_sku == sku.lower()}")
        if p.canonical_sku:
            print(f"p.canonical_sku.lower() == '{sku.lower()}': {p.canonical_sku.lower() == sku.lower()}")

if __name__ == "__main__":
    asyncio.run(check())


