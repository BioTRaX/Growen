#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_sql_perf.py
# NG-HEADER: Ubicación: tests/performance/test_market_sql_perf.py
# NG-HEADER: Descripción: Tests de performance de consultas SQL para módulo Mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests de performance para consultas SQL del módulo Mercado.

Valida:
- Ausencia de N+1 queries
- Uso de índices apropiados
- Tiempo de respuesta de consultas con volumen
- Eficiencia de joins y eager loading
"""

from __future__ import annotations

import time
import pytest
import pytest_asyncio
from decimal import Decimal
from typing import List

from sqlalchemy import select, func, text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from db.models import CanonicalProduct, MarketSource, Category, Supplier
from services.routers.market import list_market_products

# test_category y db vienen de tests/performance/conftest.py


@pytest_asyncio.fixture
async def large_product_dataset(
    db: AsyncSession,
    test_category: Category
) -> List[int]:
    """
    Crea dataset grande de productos para tests de performance SQL.
    
    Crea:
    - 100 productos
    - 3 fuentes por producto (300 fuentes total)
    - Distribuidos en 5 categorías
    """
    print("\n[Fixture] Creando dataset de 100 productos con fuentes...")
    
    product_ids = []
    
    # Crear 5 categorías adicionales
    categories = [test_category]
    for i in range(4):
        cat = Category(
            name=f"Categoría SQL Test {i+2}"
        )
        db.add(cat)
        categories.append(cat)
    
    await db.flush()
    
    # Crear 100 productos con fuentes
    for i in range(100):
        product = CanonicalProduct(
            name=f"Producto SQL Test {i+1:03d}",
            ng_sku=f"SQL-TEST-{i+1:04d}",
            category_id=categories[i % 5].id,
            sale_price=Decimal("100.00") + Decimal(str(i)),
            market_price_reference=Decimal("110.00") + Decimal(str(i)),
        )
        db.add(product)
        await db.flush()
        
        # Crear 3 fuentes por producto
        for j in range(3):
            source = MarketSource(
                product_id=product.id,
                source_name=f"Fuente {j+1}",
                url=f"https://example.com/product/{product.id}/source/{j+1}",
                source_type="static",
                is_mandatory=(j == 0),
            )
            db.add(source)
        
        product_ids.append(product.id)
    
    await db.commit()
    
    print(f"  ✓ Creados {len(product_ids)} productos con {len(product_ids) * 3} fuentes")
    return product_ids


@pytest.mark.asyncio
@pytest.mark.performance
async def test_no_nplus1_when_loading_products_with_sources(
    db: AsyncSession,
    large_product_dataset: List[int]
):
    """
    Valida que no hay N+1 queries al cargar productos con sus fuentes.
    
    Criterios:
    - Usar eager loading (joinedload/selectinload)
    - Número de queries independiente del número de productos
    - Query count <= 3 (productos + fuentes + categorías)
    """
    print("\n" + "="*70)
    print("TEST SQL: Detección de N+1 Queries")
    print("="*70)
    
    # Habilitar logging de queries SQL para contar
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    
    query_count = {'count': 0, 'queries': []}
    
    def count_queries(conn, cursor, statement, parameters, context, executemany):
        query_count['count'] += 1
        # Guardar query sin parámetros para debugging
        query_text = statement[:100] if len(statement) > 100 else statement
        query_count['queries'].append(query_text)
    
    # Hook temporal para contar queries
    event.listen(db.bind.sync_engine, "before_cursor_execute", count_queries)
    
    try:
        print("\n[1/4] Ejecutando query CON eager loading...")
        query_count['count'] = 0
        query_count['queries'] = []
        
        # Query optimizada con eager loading
        query = (
            select(CanonicalProduct)
            .options(
                selectinload(CanonicalProduct.category),
                selectinload(CanonicalProduct.market_sources)
            )
            .limit(50)
        )
        
        result = await db.execute(query)
        products = result.scalars().all()
        
        # Acceder a las relaciones para forzar carga
        for product in products:
            _ = product.category  # Acceso a categoría
            _ = list(product.market_sources)  # Acceso a fuentes
        
        queries_with_eager = query_count['count']
        print(f"  → Queries ejecutadas: {queries_with_eager}")
        print(f"  → Productos cargados: {len(products)}")
        
        # Mostrar primeras queries
        print(f"\n  Queries ejecutadas:")
        for idx, q in enumerate(query_count['queries'][:5], 1):
            print(f"    {idx}. {q}...")
        
        print("\n[2/4] Ejecutando query SIN eager loading (para comparación)...")
        query_count['count'] = 0
        query_count['queries'] = []
        
        # Query sin optimización
        query_bad = select(CanonicalProduct).limit(50)
        result_bad = await db.execute(query_bad)
        products_bad = result_bad.scalars().all()
        
        # Acceder a relaciones (esto causará N+1)
        for product in products_bad:
            try:
                _ = product.category
                _ = list(product.market_sources)
            except:
                pass  # Puede fallar por lazy loading en async
        
        queries_without_eager = query_count['count']
        print(f"  → Queries ejecutadas: {queries_without_eager}")
        print(f"  → Productos cargados: {len(products_bad)}")
        
        print("\n[3/4] Comparación:")
        print(f"  → CON eager loading: {queries_with_eager} queries")
        print(f"  → SIN eager loading: {queries_without_eager} queries")
        
        if queries_without_eager > queries_with_eager:
            reduction = ((queries_without_eager - queries_with_eager) / queries_without_eager) * 100
            print(f"  → Reducción de queries: {reduction:.1f}%")
        
        print("\n[4/4] Validando criterios:")
        
        # Criterio 1: Con eager loading debe usar <= 5 queries (margen de seguridad)
        print(f"\n  Criterio 1: Queries con eager loading <= 5")
        print(f"    → Resultado: {queries_with_eager} queries")
        assert queries_with_eager <= 5, \
            f"Demasiadas queries con eager loading: {queries_with_eager} (esperado <= 5)"
        print(f"    ✓ PASÓ")
        
        # Criterio 2: Eager loading debe ser significativamente mejor
        if queries_without_eager > 0:
            print(f"\n  Criterio 2: Eager loading reduce queries")
            improvement = queries_without_eager > queries_with_eager
            print(f"    → {queries_without_eager} (sin) > {queries_with_eager} (con)")
            assert improvement, "Eager loading no redujo el número de queries"
            print(f"    ✓ PASÓ")
        
    finally:
        # Remover listener
        event.remove(db.bind.sync_engine, "before_cursor_execute", count_queries)
    
    print("\n" + "="*70)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_market_products_query_performance(
    db: AsyncSession,
    large_product_dataset: List[int]
):
    """
    Valida performance de la query principal de list_market_products.
    
    Criterios:
    - Query completa en < 500ms con 100 productos
    - Paginación eficiente
    - Filtros no degradan performance significativamente
    """
    print("\n" + "="*70)
    print("TEST SQL: Performance de list_market_products")
    print("="*70)
    
    print("\n[1/4] Query sin filtros (página 1)...")
    start = time.time()
    
    result = await list_market_products(
        q=None,
        category_id=None,
        supplier_id=None,
        page=1,
        page_size=50,
        db=db
    )
    
    duration_no_filter = (time.time() - start) * 1000  # ms
    print(f"  → Duración: {duration_no_filter:.2f}ms")
    print(f"  → Productos retornados: {len(result.items)}/{result.total}")
    print(f"  → Páginas totales: {result.pages}")
    
    print("\n[2/4] Query con filtro de búsqueda...")
    start = time.time()
    
    result_filtered = await list_market_products(
        q="Producto SQL Test 050",
        category_id=None,
        supplier_id=None,
        page=1,
        page_size=50,
        db=db
    )
    
    duration_with_filter = (time.time() - start) * 1000  # ms
    print(f"  → Duración: {duration_with_filter:.2f}ms")
    print(f"  → Productos encontrados: {len(result_filtered.items)}")
    
    print("\n[3/4] Query con paginación (página 2)...")
    start = time.time()
    
    result_page2 = await list_market_products(
        q=None,
        category_id=None,
        supplier_id=None,
        page=2,
        page_size=50,
        db=db
    )
    
    duration_page2 = (time.time() - start) * 1000  # ms
    print(f"  → Duración página 2: {duration_page2:.2f}ms")
    print(f"  → Productos retornados: {len(result_page2.items)}")
    
    print("\n[4/4] Validando criterios:")
    
    # Criterio 1: Query sin filtro < 500ms
    print(f"\n  Criterio 1: Query sin filtro < 500ms")
    print(f"    → Resultado: {duration_no_filter:.2f}ms")
    assert duration_no_filter < 500, f"Query muy lenta: {duration_no_filter:.2f}ms"
    print(f"    ✓ PASÓ")
    
    # Criterio 2: Filtro no degrada más del 50%
    degradation = (duration_with_filter / duration_no_filter) * 100 - 100
    print(f"\n  Criterio 2: Filtro no degrada > 50%")
    print(f"    → Degradación: {degradation:.1f}%")
    assert degradation < 50, f"Filtro degrada demasiado: {degradation:.1f}%"
    print(f"    ✓ PASÓ")
    
    # Criterio 3: Paginación consistente
    variation = abs(duration_page2 - duration_no_filter) / duration_no_filter * 100
    print(f"\n  Criterio 3: Paginación consistente (variación < 30%)")
    print(f"    → Variación: {variation:.1f}%")
    assert variation < 30, f"Variación de paginación: {variation:.1f}%"
    print(f"    ✓ PASÓ")
    
    print("\n" + "="*70)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_database_indexes_exist(db: AsyncSession):
    """
    Verifica que existen índices apropiados en las tablas críticas.
    
    Índices esperados:
    - market_sources.product_id (FK index)
    - canonical_products.category_id (FK index)
    - canonical_products.name (para búsquedas)
    - market_sources.last_scraped_at (para ordenamiento temporal)
    """
    print("\n" + "="*70)
    print("TEST SQL: Verificación de Índices")
    print("="*70)
    
    # Obtener información de índices desde el inspector
    # Para AsyncEngine, necesitamos usar run_sync
    from sqlalchemy import inspect as sync_inspect
    
    print("\n[1/3] Verificando índices en tabla 'canonical_products'...")
    product_indexes = await db.run_sync(
        lambda conn: sync_inspect(conn).get_indexes('canonical_products')
    )
    
    print(f"  → Índices encontrados: {len(product_indexes)}")
    for idx in product_indexes:
        print(f"    - {idx['name']}: columnas={idx['column_names']}, unique={idx.get('unique', False)}")
    
    # Verificar índices críticos
    index_names = [idx['name'] for idx in product_indexes]
    indexed_columns = set()
    for idx in product_indexes:
        indexed_columns.update(idx['column_names'])
    
    print(f"\n  Columnas indexadas: {sorted(indexed_columns)}")
    
    # Criterio: category_id debe estar indexada
    assert 'category_id' in indexed_columns, "Falta índice en canonical_products.category_id"
    print(f"  ✓ category_id está indexada")
    
    print("\n[2/3] Verificando índices en tabla 'market_sources'...")
    source_indexes = await db.run_sync(
        lambda conn: sync_inspect(conn).get_indexes('market_sources')
    )
    
    print(f"  → Índices encontrados: {len(source_indexes)}")
    for idx in source_indexes:
        print(f"    - {idx['name']}: columnas={idx['column_names']}, unique={idx.get('unique', False)}")
    
    source_indexed_columns = set()
    for idx in source_indexes:
        source_indexed_columns.update(idx['column_names'])
    
    print(f"\n  Columnas indexadas: {sorted(source_indexed_columns)}")
    
    # Criterio: product_id debe estar indexada
    assert 'product_id' in source_indexed_columns, "Falta índice en market_sources.product_id"
    print(f"  ✓ product_id está indexada")
    
    print("\n[3/3] Recomendaciones de optimización:")
    
    # Índices recomendados adicionales
    recommendations = []
    
    if 'name' not in indexed_columns:
        recommendations.append("CREATE INDEX idx_products_name ON canonical_products(name);")
    
    if 'ng_sku' not in indexed_columns:
        recommendations.append("CREATE INDEX idx_products_ng_sku ON canonical_products(ng_sku);")
    
    if 'last_scraped_at' not in source_indexed_columns:
        recommendations.append("CREATE INDEX idx_sources_last_scraped ON market_sources(last_scraped_at);")
    
    if recommendations:
        print("\n  Índices adicionales recomendados:")
        for rec in recommendations:
            print(f"    → {rec}")
    else:
        print("\n  ✓ Todos los índices recomendados están presentes")
    
    print("\n" + "="*70)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_count_query_optimization(
    db: AsyncSession,
    large_product_dataset: List[int]
):
    """
    Valida que las queries de conteo (COUNT) están optimizadas.
    
    Criterios:
    - COUNT(*) no debe cargar datos completos
    - Debe ser significativamente más rápido que SELECT *
    """
    print("\n" + "="*70)
    print("TEST SQL: Optimización de COUNT Queries")
    print("="*70)
    
    print("\n[1/3] Ejecutando COUNT query...")
    start = time.time()
    
    count_query = select(func.count()).select_from(CanonicalProduct)
    count_result = await db.scalar(count_query)
    
    count_duration = (time.time() - start) * 1000  # ms
    print(f"  → Duración: {count_duration:.2f}ms")
    print(f"  → Total productos: {count_result}")
    
    print("\n[2/3] Ejecutando SELECT query completa...")
    start = time.time()
    
    select_query = select(CanonicalProduct)
    select_result = await db.execute(select_query)
    products = select_result.scalars().all()
    
    select_duration = (time.time() - start) * 1000  # ms
    print(f"  → Duración: {select_duration:.2f}ms")
    print(f"  → Productos cargados: {len(products)}")
    
    print("\n[3/3] Comparación:")
    speedup = select_duration / count_duration
    print(f"  → COUNT: {count_duration:.2f}ms")
    print(f"  → SELECT: {select_duration:.2f}ms")
    print(f"  → Speedup de COUNT: {speedup:.2f}x más rápido")
    
    # Criterio: COUNT debe ser al menos 2x más rápido
    assert speedup >= 2, f"COUNT no es significativamente más rápido: {speedup:.2f}x"
    print(f"\n  ✓ PASÓ: COUNT es {speedup:.2f}x más rápido que SELECT")
    
    print("\n" + "="*70)
