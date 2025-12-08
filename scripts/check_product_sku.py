#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_product_sku.py
# NG-HEADER: Ubicación: scripts/check_product_sku.py
# NG-HEADER: Descripción: Script para verificar el SKU de un producto en la base de datos.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Script para verificar el SKU de un producto en la base de datos."""

import asyncio
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from db.models import Product
from agent_core.config import settings

load_dotenv()

async def check_product_sku(product_id: int = None, sku_search: str = None):
    """Verifica el SKU de un producto en la base de datos.
    
    Args:
        product_id: ID del producto a consultar.
        sku_search: SKU a buscar (opcional).
    """
    # Construir URL de conexión
    db_url = os.getenv("DB_URL") or settings.db_url
    engine = create_async_engine(db_url, echo=False)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        if product_id:
            # Buscar por ID
            product = await session.get(Product, product_id)
            if product:
                print(f"\n=== Producto ID {product_id} ===")
                print(f"sku_root: '{product.sku_root}'")
                print(f"canonical_sku: '{product.canonical_sku}'")
                print(f"title: '{product.title}'")
                print(f"ID: {product.id}")
                
                # Verificar si el SKU coincide con el buscado
                if sku_search:
                    print(f"\n=== Comparación con SKU buscado: '{sku_search}' ===")
                    print(f"sku_root == '{sku_search}': {product.sku_root == sku_search}")
                    print(f"canonical_sku == '{sku_search}': {product.canonical_sku == sku_search}")
                    print(f"sku_root.lower() == '{sku_search.lower()}': {product.sku_root.lower() == sku_search.lower()}")
                    print(f"canonical_sku.lower() == '{sku_search.lower()}': {product.canonical_sku and product.canonical_sku.lower() == sku_search.lower()}")
            else:
                print(f"Producto con ID {product_id} no encontrado")
        
        if sku_search and not product_id:
            # Buscar por SKU
            print(f"\n=== Búsqueda por SKU: '{sku_search}' ===")
            
            # Buscar por canonical_sku
            result = await session.execute(
                select(Product).where(Product.canonical_sku == sku_search)
            )
            product = result.scalar_one_or_none()
            if product:
                print(f"✓ Encontrado por canonical_sku:")
                print(f"  ID: {product.id}")
                print(f"  sku_root: '{product.sku_root}'")
                print(f"  canonical_sku: '{product.canonical_sku}'")
                print(f"  title: '{product.title}'")
            else:
                print(f"✗ NO encontrado por canonical_sku='{sku_search}'")
            
            # Buscar por sku_root
            result = await session.execute(
                select(Product).where(Product.sku_root == sku_search)
            )
            product = result.scalar_one_or_none()
            if product:
                print(f"✓ Encontrado por sku_root:")
                print(f"  ID: {product.id}")
                print(f"  sku_root: '{product.sku_root}'")
                print(f"  canonical_sku: '{product.canonical_sku}'")
                print(f"  title: '{product.title}'")
            else:
                print(f"✗ NO encontrado por sku_root='{sku_search}'")
            
            # Buscar case-insensitive
            from sqlalchemy import func
            result = await session.execute(
                select(Product).where(
                    func.lower(Product.canonical_sku) == sku_search.lower()
                )
            )
            product = result.scalar_one_or_none()
            if product:
                print(f"⚠ Encontrado por canonical_sku (case-insensitive):")
                print(f"  ID: {product.id}")
                print(f"  sku_root: '{product.sku_root}'")
                print(f"  canonical_sku: '{product.canonical_sku}'")
                print(f"  title: '{product.title}'")
            else:
                result = await session.execute(
                    select(Product).where(
                        func.lower(Product.sku_root) == sku_search.lower()
                    )
                )
                product = result.scalar_one_or_none()
                if product:
                    print(f"⚠ Encontrado por sku_root (case-insensitive):")
                    print(f"  ID: {product.id}")
                    print(f"  sku_root: '{product.sku_root}'")
                    print(f"  canonical_sku: '{product.canonical_sku}'")
                    print(f"  title: '{product.title}'")
                else:
                    print(f"✗ NO encontrado ni con búsqueda case-insensitive")
    
    await engine.dispose()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verificar SKU de producto en la base de datos")
    parser.add_argument("--product-id", type=int, help="ID del producto a consultar")
    parser.add_argument("--sku", type=str, help="SKU a buscar")
    
    args = parser.parse_args()
    
    if not args.product_id and not args.sku:
        print("Error: Debe proporcionar --product-id o --sku")
        sys.exit(1)
    
    asyncio.run(check_product_sku(product_id=args.product_id, sku_search=args.sku))

