#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_query_builder.py
# NG-HEADER: Ubicación: test_query_builder.py
# NG-HEADER: Descripción: Test rápido de construcción de queries de búsqueda
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Test rápido para validar que build_search_query genera queries correctas.
"""

from workers.discovery.source_finder import build_search_query


def test_queries():
    """Prueba diferentes casos de construcción de query."""
    
    print("🔍 Probando construcción de queries de búsqueda\n")
    
    # Caso 1: Solo nombre canónico
    query1 = build_search_query("Filtros Libella Slim")
    print(f"Test 1 - Solo nombre:")
    print(f"  Input:  product_name='Filtros Libella Slim'")
    print(f"  Output: '{query1}'")
    print(f"  ✅ OK\n" if query1 == "Filtros Libella Slim comprar" else f"  ❌ FAIL\n")
    
    # Caso 2: Con categoría (debe ignorarse)
    query2 = build_search_query("Filtros Libella Slim", category="Parafernalia")
    print(f"Test 2 - Con categoría (debe ignorarse):")
    print(f"  Input:  product_name='Filtros Libella Slim', category='Parafernalia'")
    print(f"  Output: '{query2}'")
    print(f"  ✅ OK\n" if query2 == "Filtros Libella Slim comprar" else f"  ❌ FAIL\n")
    
    # Caso 3: Con SKU (debe ignorarse)
    query3 = build_search_query("Carpa Indoor 80x80", sku="CAMP_0001_CAR")
    print(f"Test 3 - Con SKU (debe ignorarse):")
    print(f"  Input:  product_name='Carpa Indoor 80x80', sku='CAMP_0001_CAR'")
    print(f"  Output: '{query3}'")
    print(f"  ✅ OK\n" if query3 == "Carpa Indoor 80x80 comprar" else f"  ❌ FAIL\n")
    
    # Caso 4: Producto con espacios extra
    query4 = build_search_query("  Fertilizante Top Crop   ")
    print(f"Test 4 - Nombre con espacios extra:")
    print(f"  Input:  product_name='  Fertilizante Top Crop   '")
    print(f"  Output: '{query4}'")
    print(f"  ✅ OK\n" if query4 == "Fertilizante Top Crop comprar" else f"  ❌ FAIL\n")
    
    # Caso 5: Nombre vacío (debe fallar)
    print(f"Test 5 - Nombre vacío (debe lanzar ValueError):")
    try:
        query5 = build_search_query("")
        print(f"  ❌ FAIL: No lanzó excepción\n")
    except ValueError as e:
        print(f"  ✅ OK: Lanzó ValueError -> {e}\n")
    
    print("=" * 60)
    print("🎯 Resumen:")
    print("  - Query simplificada: '{nombre_canonico} comprar'")
    print("  - Categoría y SKU se ignoran (reducen ruido)")
    print("  - 'precio' eliminado (redundante)")


if __name__ == "__main__":
    test_queries()
