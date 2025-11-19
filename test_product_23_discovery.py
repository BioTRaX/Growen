#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_product_23_discovery.py
# NG-HEADER: Ubicación: test_product_23_discovery.py
# NG-HEADER: Descripción: Test real del endpoint de descubrimiento para producto 23
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Test del endpoint discover-sources con el producto 23 real.
"""

import asyncio
import httpx
from db.session import SessionLocal
from sqlalchemy import select
from db.models import CanonicalProduct
from workers.discovery.source_finder import discover_price_sources


async def test_product_23():
    """Prueba descubrimiento directo sin pasar por endpoint HTTP."""
    
    print("=" * 70)
    print("🔍 TEST: Descubrimiento de Fuentes - Producto 23")
    print("=" * 70)
    
    # 1. Obtener datos del producto 23 desde la DB
    async with SessionLocal() as db:
        query = (
            select(CanonicalProduct)
            .where(CanonicalProduct.id == 23)
        )
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            print("❌ Producto 23 no encontrado en la base de datos")
            return
        
        print(f"\n📦 Producto encontrado:")
        print(f"  ID: {product.id}")
        print(f"  Nombre: {product.name}")
        print(f"  SKU: {product.ng_sku}")
        
        # Obtener categoría si existe
        category_name = ""
        if product.category_id:
            from db.models import Category
            cat_query = select(Category).where(Category.id == product.category_id)
            cat_result = await db.execute(cat_query)
            category = cat_result.scalar_one_or_none()
            if category:
                category_name = category.name
                print(f"  Categoría: {category_name}")
        
        # 2. Llamar al descubridor
        print(f"\n🔎 Iniciando descubrimiento...")
        print(f"  Query esperada: '{product.name} comprar'")
        
        result = await discover_price_sources(
            product_name=product.name,
            category=category_name,
            sku=product.ng_sku or "",
            existing_urls=[],
            max_results=10,
            user_role="admin"
        )
        
        print(f"\n📊 Resultados:")
        print(f"  Success: {result['success']}")
        print(f"  Query usada: '{result['query']}'")
        print(f"  Total resultados MCP: {result['total_results']}")
        print(f"  Fuentes válidas: {result['valid_sources']}")
        
        if result['valid_sources'] > 0:
            print(f"\n✅ Fuentes encontradas ({len(result['sources'])}):")
            for i, source in enumerate(result['sources'][:5], 1):
                print(f"\n  {i}. {source['title']}")
                print(f"     URL: {source['url']}")
                snippet = source.get('snippet', '')[:80]
                if snippet:
                    print(f"     Snippet: {snippet}...")
        else:
            print(f"\n❌ No se encontraron fuentes válidas")
            if 'error' in result:
                print(f"  Error: {result['error']}")
        
        print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_product_23())
