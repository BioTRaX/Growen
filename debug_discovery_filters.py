#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: debug_discovery_filters.py
# NG-HEADER: Ubicación: debug_discovery_filters.py
# NG-HEADER: Descripción: Debug de filtros de descubrimiento
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Debug: Muestra qué URLs se rechazan y por qué.
"""

import asyncio
import platform
from workers.discovery.source_finder import (
    call_mcp_web_search,
    is_valid_ecommerce_url,
    has_price_indicators,
    is_excluded_url,
    KNOWN_ECOMMERCE_DOMAINS
)


async def debug_filters():
    """Analiza resultados del MCP y muestra por qué se rechazan."""
    
    print("=" * 80)
    print("🔍 DEBUG: Análisis de Filtros de Descubrimiento")
    print("=" * 80)
    
    # Query del caso real
    query = "Filtros Libella Slim comprar"
    
    print(f"\n📋 Query: '{query}'")
    print(f"🌐 Max resultados: 20")
    
    # Obtener resultados del MCP
    result = await call_mcp_web_search(query, max_results=20, user_role="admin")
    
    if "error" in result:
        print(f"\n❌ Error: {result['error']}")
        return
    
    items = result.get("items", [])
    print(f"\n✅ MCP retornó {len(items)} resultados\n")
    
    # Analizar cada resultado
    for i, item in enumerate(items, 1):
        url = item.get("url", "")
        title = item.get("title", "Sin título")[:60]
        snippet = item.get("snippet", "")[:80]
        
        print(f"\n{'=' * 80}")
        print(f"Resultado #{i}: {title}")
        print(f"URL: {url}")
        print(f"Snippet: {snippet}...")
        
        # Validaciones
        checks = []
        
        # 1. URL válida
        if not url:
            checks.append("❌ URL vacía")
        else:
            checks.append("✅ URL presente")
        
        # 2. Título válido
        if not title or title == "Sin título":
            checks.append("❌ Título vacío")
        else:
            checks.append("✅ Título presente")
        
        # 3. URL excluida
        if is_excluded_url(url):
            checks.append("❌ URL excluida (imagen/estático)")
        else:
            checks.append("✅ URL no excluida")
        
        # 4. Dominio e-commerce
        if is_valid_ecommerce_url(url):
            checks.append("✅ Dominio e-commerce válido")
        else:
            checks.append("❌ Dominio NO está en lista conocida")
        
        # 5. Indicadores de precio
        if has_price_indicators(snippet):
            checks.append("✅ Tiene indicadores de precio")
        else:
            checks.append("❌ Sin indicadores de precio en snippet")
        
        # Mostrar checks
        print("\n📊 Validaciones:")
        for check in checks:
            print(f"  {check}")
        
        # Decisión final
        passed_all = all("✅" in c for c in checks)
        if passed_all:
            print("\n🎯 RESULTADO: ✅ ACEPTADA")
        else:
            print("\n🎯 RESULTADO: ❌ RECHAZADA")
    
    # Resumen de dominios conocidos
    print(f"\n\n{'=' * 80}")
    print("📚 DOMINIOS CONOCIDOS ACTUALMENTE ({} dominios)".format(len(KNOWN_ECOMMERCE_DOMAINS)))
    print("=" * 80)
    for domain in sorted(KNOWN_ECOMMERCE_DOMAINS):
        print(f"  • {domain}")
    
    print("\n" + "=" * 80)
    print("💡 RECOMENDACIÓN")
    print("=" * 80)
    print("Si muchos resultados se rechazan por 'Dominio NO está en lista conocida',")
    print("considera una de estas soluciones:")
    print("  1. Agregar más dominios a KNOWN_ECOMMERCE_DOMAINS")
    print("  2. Usar heurística más flexible (detectar '.com.ar', '.tienda', etc.)")
    print("  3. Relajar filtro para permitir más dominios con indicadores de precio")
    print("=" * 80)


if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(debug_filters())
