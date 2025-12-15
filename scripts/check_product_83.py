#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_product_83.py
# NG-HEADER: Ubicación: scripts/check_product_83.py
# NG-HEADER: Descripción: Script temporal para verificar producto 83 y búsqueda por SKU.
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
from sqlalchemy import select, func

async def check():
    async with SessionLocal() as db:
        # Verificar producto 83
        p = await db.scalar(select(Product).where(Product.id == 83))
        if p:
            print(f"=== Producto ID 83 ===")
            print(f"canonical_sku: {repr(p.canonical_sku)}")
            print(f"sku_root: {repr(p.sku_root)}")
            print(f"title: {p.title}")
            print()
        
        # Buscar por canonical_sku
        p1 = await db.scalar(select(Product).where(Product.canonical_sku == 'PAR_0005_BAN'))
        print(f"Búsqueda por canonical_sku='PAR_0005_BAN': {p1.id if p1 else 'NO ENCONTRADO'}")
        
        # Buscar por sku_root
        p2 = await db.scalar(select(Product).where(Product.sku_root == 'PAR_0005_BAN'))
        print(f"Búsqueda por sku_root='PAR_0005_BAN': {p2.id if p2 else 'NO ENCONTRADO'}")
        
        # Buscar case-insensitive
        p3 = await db.scalar(
            select(Product).where(
                func.lower(Product.canonical_sku) == 'par_0005_ban'.lower()
            )
        )
        print(f"Búsqueda case-insensitive canonical_sku: {p3.id if p3 else 'NO ENCONTRADO'}")
        
        p4 = await db.scalar(
            select(Product).where(
                func.lower(Product.sku_root) == 'par_0005_ban'.lower()
            )
        )
        print(f"Búsqueda case-insensitive sku_root: {p4.id if p4 else 'NO ENCONTRADO'}")

if __name__ == "__main__":
    asyncio.run(check())













