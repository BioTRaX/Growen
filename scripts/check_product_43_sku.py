#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_product_43_sku.py
# NG-HEADER: Ubicación: scripts/check_product_43_sku.py
# NG-HEADER: Descripción: Verifica SKU del producto 43
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Script para verificar SKU del producto 43."""

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from db.session import SessionLocal
from db.models import Product
from sqlalchemy import select, func, or_

async def check():
    async with SessionLocal() as db:
        product_id = 43
        sku_to_check = 'PES_0009_QUI'
        
        p = await db.get(Product, product_id)
        if not p:
            print(f"Producto {product_id}: NO ENCONTRADO")
            return
        
        print(f"=== Producto {product_id}: {p.title} ===")
        print(f"canonical_sku: {repr(p.canonical_sku)}")
        print(f"sku_root: {repr(p.sku_root)}")
        print()
        
        print(f"=== Búsquedas para SKU '{sku_to_check}' ===")
        # 1. Búsqueda exacta en canonical_sku
        p1 = await db.scalar(select(Product).where(Product.canonical_sku == sku_to_check))
        print(f"1. Product.canonical_sku == '{sku_to_check}': {p1.id if p1 else 'NO ENCONTRADO'}")
        
        # 2. Búsqueda exacta en sku_root
        p2 = await db.scalar(select(Product).where(Product.sku_root == sku_to_check))
        print(f"2. Product.sku_root == '{sku_to_check}': {p2.id if p2 else 'NO ENCONTRADO'}")
        
        # 3. Búsqueda case-insensitive en canonical_sku
        p3 = await db.scalar(
            select(Product).where(
                func.lower(Product.canonical_sku) == sku_to_check.lower()
            )
        )
        print(f"3. Product.canonical_sku (case-insensitive) == '{sku_to_check}': {p3.id if p3 else 'NO ENCONTRADO'}")
        
        # 4. Búsqueda case-insensitive en sku_root
        p4 = await db.scalar(
            select(Product).where(
                func.lower(Product.sku_root) == sku_to_check.lower()
            )
        )
        print(f"4. Product.sku_root (case-insensitive) == '{sku_to_check}': {p4.id if p4 else 'NO ENCONTRADO'}")
        print()
        
        print(f"=== Comparaciones ===")
        print(f"p.canonical_sku == '{sku_to_check}': {p.canonical_sku == sku_to_check}")
        print(f"p.sku_root == '{sku_to_check}': {p.sku_root == sku_to_check}")
        print(f"p.canonical_sku.lower() == '{sku_to_check.lower()}': {p.canonical_sku.lower() == sku_to_check.lower() if p.canonical_sku else False}")
        print(f"p.sku_root.lower() == '{sku_to_check.lower()}': {p.sku_root.lower() == sku_to_check.lower() if p.sku_root else False}")

if __name__ == "__main__":
    asyncio.run(check())

