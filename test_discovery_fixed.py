#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_discovery_fixed.py
# NG-HEADER: Ubicación: test_discovery_fixed.py
# NG-HEADER: Descripción: Test del descubrimiento con URLs decodificadas
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Test rápido para validar que las URLs se decodifican correctamente.
"""

import asyncio
import platform
from workers.discovery.source_finder import discover_price_sources


async def test_discovery():
    """Prueba descubrimiento con producto 23."""
    
    print("=" * 70)
    print("🔍 TEST: Descubrimiento con URLs Decodificadas")
    print("=" * 70)
    
    result = await discover_price_sources(
        product_name="Filtros Libella Slim",
        category="Parafernalia",
        sku="NG-000023",
        existing_urls=[],
        max_results=20,
        user_role="admin"
    )
    
    print(f"\n📊 Resultados:")
    print(f"  Success: {result['success']}")
    print(f"  Query: '{result['query']}'")
    print(f"  Total resultados MCP: {result['total_results']}")
    print(f"  Fuentes válidas: {result['valid_sources']}")
    
    if result['valid_sources'] > 0:
        print(f"\n✅ ÉXITO: Encontradas {len(result['sources'])} fuentes válidas:\n")
        for i, source in enumerate(result['sources'][:10], 1):
            print(f"  {i}. {source['title'][:60]}")
            print(f"     {source['url']}")
            print()
    else:
        print(f"\n❌ PROBLEMA: 0 fuentes válidas de {result['total_results']} resultados")
        if 'error' in result:
            print(f"  Error: {result['error']}")
    
    print("=" * 70)


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(test_discovery())
