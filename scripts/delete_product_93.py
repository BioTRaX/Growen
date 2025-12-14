#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: delete_product_93.py
# NG-HEADER: Ubicación: scripts/delete_product_93.py
# NG-HEADER: Descripción: Script para eliminar producto 93 (testing) manualmente
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Script para eliminar el producto 93 que es de testing.

Verifica si existe como Product interno o CanonicalProduct y lo elimina apropiadamente.
"""

import asyncio
import sys
from db.session import SessionLocal
from db.models import Product, CanonicalProduct
from sqlalchemy import select

async def delete_product_93():
    """Elimina el producto 93 si existe."""
    async with SessionLocal() as session:
        # Verificar si existe como Product interno
        product = await session.get(Product, 93)
        if product:
            print(f"✅ Encontrado Product interno ID 93: {product.title}")
            print(f"   SKU: {product.sku_root}")
            print(f"   Stock: {product.stock}")
            
            # Verificar stock y referencias
            if product.stock and product.stock > 0:
                print(f"⚠️  ADVERTENCIA: El producto tiene stock {product.stock}")
                response = input("¿Deseas eliminarlo de todas formas? (s/N): ")
                if response.lower() != 's':
                    print("❌ Cancelado")
                    return
            
            # Eliminar
            await session.delete(product)
            await session.commit()
            print("✅ Product interno 93 eliminado")
            return
        
        # Verificar si existe como CanonicalProduct
        canonical = await session.get(CanonicalProduct, 93)
        if canonical:
            print(f"✅ Encontrado CanonicalProduct ID 93: {canonical.name}")
            print(f"   SKU: {canonical.sku_custom or canonical.ng_sku}")
            
            response = input("¿Deseas eliminar este CanonicalProduct? (s/N): ")
            if response.lower() != 's':
                print("❌ Cancelado")
                return
            
            await session.delete(canonical)
            await session.commit()
            print("✅ CanonicalProduct 93 eliminado")
            return
        
        print("❌ No se encontró ningún producto con ID 93")
        print("   (Ni Product interno ni CanonicalProduct)")

if __name__ == "__main__":
    asyncio.run(delete_product_93())

