#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_discovery_debug.py
# NG-HEADER: Ubicación: test_discovery_debug.py
# NG-HEADER: Descripción: Debug completo del proceso de descubrimiento de fuentes
# NG-HEADER: Lineamientos: Ver AGENTS.md

import asyncio
import logging

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)

from workers.discovery.source_finder import discover_price_sources

async def main():
    print("=" * 80)
    print("🔍 TEST DE DESCUBRIMIENTO DE FUENTES - DEBUG COMPLETO")
    print("=" * 80)
    
    # Producto 23: Filtros Libella Slim
    product_name = "Filtros Libella Slim"
    category = "Parafernalia"
    sku = ""
    
    print(f"\n📦 Producto: {product_name}")
    print(f"📂 Categoría: {category}")
    print(f"🏷️  SKU: {sku or 'N/A'}")
    print(f"🔢 Max resultados: 20")
    print()
    
    result = await discover_price_sources(
        product_name=product_name,
        category=category,
        sku=sku,
        max_results=20
    )
    
    print("\n" + "=" * 80)
    print("📊 RESULTADO DEL DESCUBRIMIENTO")
    print("=" * 80)
    
    print(f"\n✅ Éxito: {result.get('success')}")
    print(f"🔍 Query usada: {result.get('query')}")
    print(f"📥 Total resultados MCP: {result.get('total_results')}")
    print(f"✔️  Fuentes válidas: {result.get('valid_sources')}")
    
    if result.get("error"):
        print(f"\n❌ ERROR: {result['error']}")
    
    sources = result.get("sources", [])
    
    if sources:
        print(f"\n📋 FUENTES ENCONTRADAS ({len(sources)}):")
        print("-" * 80)
        for i, source in enumerate(sources, 1):
            print(f"\n{i}. {source['title'][:70]}")
            print(f"   URL: {source['url']}")
            print(f"   Snippet: {source['snippet'][:100]}...")
    else:
        print("\n⚠️  NO SE ENCONTRARON FUENTES VÁLIDAS")
        print("\nPosibles razones:")
        print("  1. MCP no devolvió resultados")
        print("  2. Resultados no pasaron filtro de dominios conocidos")
        print("  3. Resultados no tenían indicadores de precio")
        print("  4. URLs fueron excluidas por patrones (imágenes, estáticos)")

if __name__ == "__main__":
    asyncio.run(main())
