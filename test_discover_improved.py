#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_discover_improved.py
# NG-HEADER: Ubicación: test_discover_improved.py
# NG-HEADER: Descripción: Test de descubrimiento con query mejorada
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Test para validar que la query simplificada mejora los resultados de descubrimiento.
"""

import asyncio
from workers.discovery.source_finder import call_mcp_web_search


async def test_improved_query():
    """Compara resultados entre query antigua y nueva."""
    
    print("=" * 70)
    print("🔬 TEST: Query Simplificada vs Query Antigua")
    print("=" * 70)
    
    # Query NUEVA (simplificada)
    query_nueva = "Filtros Libella Slim comprar"
    
    # Query ANTIGUA (con ruido)
    query_antigua = "Filtros Libella Slim Parafernalia precio comprar"
    
    print("\n📋 Configuración del test:")
    print(f"  Producto: Filtros Libella Slim")
    print(f"  Categoría: Parafernalia")
    print(f"  Max resultados: 10")
    
    print("\n" + "=" * 70)
    print("1️⃣  QUERY NUEVA (simplificada)")
    print("=" * 70)
    print(f"Query: '{query_nueva}'")
    print("\nLlamando a MCP Web Search...")
    
    result_nueva = await call_mcp_web_search(
        query=query_nueva,
        max_results=10,
        user_role="admin"
    )
    
    if "error" in result_nueva:
        print(f"❌ Error: {result_nueva['error']}")
        items_nueva = []
    else:
        items_nueva = result_nueva.get("items", [])
        print(f"✅ Encontrados {len(items_nueva)} resultados")
        
        if items_nueva:
            print("\n📦 Top 5 resultados:")
            for i, item in enumerate(items_nueva[:5], 1):
                title = item.get("title", "Sin título")[:60]
                url = item.get("url", "N/A")
                snippet = item.get("snippet", "")[:80]
                print(f"\n  {i}. {title}")
                print(f"     URL: {url}")
                if snippet:
                    print(f"     Snippet: {snippet}...")
    
    print("\n" + "=" * 70)
    print("2️⃣  QUERY ANTIGUA (con categoría y 'precio')")
    print("=" * 70)
    print(f"Query: '{query_antigua}'")
    print("\nLlamando a MCP Web Search...")
    
    result_antigua = await call_mcp_web_search(
        query=query_antigua,
        max_results=10,
        user_role="admin"
    )
    
    if "error" in result_antigua:
        print(f"❌ Error: {result_antigua['error']}")
        items_antigua = []
    else:
        items_antigua = result_antigua.get("items", [])
        print(f"✅ Encontrados {len(items_antigua)} resultados")
        
        if items_antigua:
            print("\n📦 Top 5 resultados:")
            for i, item in enumerate(items_antigua[:5], 1):
                title = item.get("title", "Sin título")[:60]
                url = item.get("url", "N/A")
                snippet = item.get("snippet", "")[:80]
                print(f"\n  {i}. {title}")
                print(f"     URL: {url}")
                if snippet:
                    print(f"     Snippet: {snippet}...")
    
    print("\n" + "=" * 70)
    print("📊 COMPARACIÓN DE RESULTADOS")
    print("=" * 70)
    print(f"Query nueva:    {len(items_nueva)} resultados")
    print(f"Query antigua:  {len(items_antigua)} resultados")
    
    if len(items_nueva) > len(items_antigua):
        print(f"\n✅ MEJORA: +{len(items_nueva) - len(items_antigua)} resultados adicionales con query simplificada")
    elif len(items_nueva) == len(items_antigua):
        print(f"\n➡️  IGUAL: Ambas queries retornan {len(items_nueva)} resultados")
    else:
        print(f"\n⚠️  PEOR: {len(items_antigua) - len(items_nueva)} resultados menos con query simplificada")
    
    print("\n" + "=" * 70)
    print("💡 CONCLUSIÓN")
    print("=" * 70)
    print("La query simplificada '{nombre} comprar' debería:")
    print("  ✓ Reducir ruido (eliminar términos como categoría)")
    print("  ✓ Mejorar precisión (menos keywords = menos confusión)")
    print("  ✓ Incrementar recall (más resultados relevantes)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_improved_query())
