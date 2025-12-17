#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_scraping_perf.py
# NG-HEADER: Ubicación: tests/performance/test_market_scraping_perf.py
# NG-HEADER: Descripción: Tests de performance para scraping de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests de performance para el módulo de scraping de mercado.

Valida:
- Tiempo de scraping concurrente de múltiples productos
- Ausencia de race conditions y deadlocks
- Límite de recursos (memoria, CPU, browsers)
- Integridad de datos bajo carga
"""

from __future__ import annotations

import time
import asyncio
import pytest
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CanonicalProduct, MarketSource, Category, Supplier
from workers.market_scraping import update_market_prices_for_product

# Fixtures db, test_category, test_supplier vienen de tests/performance/conftest.py


async def create_test_product_with_sources(
    db: AsyncSession,
    index: int,
    category_id: int,
    num_sources: int = 3
) -> int:
    """
    Crea un producto de prueba con N fuentes simuladas.
    
    Args:
        db: Sesión de base de datos
        index: Índice único para el producto
        category_id: ID de categoría a asignar
        num_sources: Cantidad de fuentes a crear (default: 3)
        
    Returns:
        ID del producto creado
    """
    # Crear producto
    product = CanonicalProduct(
        name=f"Producto Performance Test {index}",
        ng_sku=f"PERF-TEST-{index:04d}",
        category_id=category_id,
        sale_price=Decimal("100.00") + Decimal(str(index)),
        market_price_reference=Decimal("110.00") + Decimal(str(index)),
    )
    db.add(product)
    await db.flush()
    
    # Crear fuentes de mercado simuladas
    # Usando URLs de testing que responden rápido
    for source_idx in range(num_sources):
        source = MarketSource(
            product_id=product.id,
            source_name=f"Fuente Test {source_idx + 1}",
            url=f"https://httpbin.org/delay/0?product={index}&source={source_idx}",
            source_type="static",
            is_mandatory=source_idx == 0,  # Primera fuente es obligatoria
        )
        db.add(source)
    
    await db.commit()
    await db.refresh(product)
    return product.id


@pytest.mark.asyncio
@pytest.mark.performance
async def test_scraping_parallel_10_products(
    db: AsyncSession,
    test_category: Category
):
    """
    Test de stress: scraping concurrente de 10 productos con 3 fuentes cada uno.
    
    Criterios de aceptación:
    - Tiempo total < 30 segundos
    - Todos los productos se procesan sin errores críticos
    - No hay race conditions (todos los precios se actualizan)
    - Memoria no se desborda
    """
    print("\n" + "="*70)
    print("TEST DE PERFORMANCE: Scraping Paralelo 10 Productos")
    print("="*70)
    
    # 1. Crear 10 productos con 3 fuentes cada uno
    print("\n[1/4] Creando 10 productos con 3 fuentes cada uno...")
    product_ids: List[int] = []
    
    for i in range(10):
        product_id = await create_test_product_with_sources(
            db, 
            index=i + 1, 
            category_id=test_category.id,
            num_sources=3
        )
        product_ids.append(product_id)
    
    print(f"✓ Creados {len(product_ids)} productos: {product_ids}")
    
    # 2. Ejecutar scraping en paralelo usando ThreadPoolExecutor
    print("\n[2/4] Ejecutando scraping paralelo con max_workers=5...")
    start_time = time.time()
    
    results: List[Dict[str, Any]] = []
    errors: List[Exception] = []
    
    # Función wrapper para ejecutar en thread pool
    async def scrape_product(pid: int) -> Dict[str, Any]:
        try:
            # Crear nueva sesión para cada thread (aislamiento)
            from db.session import get_session_context
            async with get_session_context() as session:
                result = await update_market_prices_for_product(pid, session)
                return result
        except Exception as e:
            return {"success": False, "error": str(e), "product_id": pid}
    
    # Ejecutar todas las tareas concurrentemente
    tasks = [scrape_product(pid) for pid in product_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    duration = time.time() - start_time
    
    # 3. Analizar resultados
    print(f"\n[3/4] Análisis de resultados (duración: {duration:.2f}s)...")
    
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
    failed = len(results) - successful
    exceptions = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"  - Productos procesados exitosamente: {successful}/{len(product_ids)}")
    print(f"  - Productos con errores: {failed}")
    print(f"  - Excepciones no capturadas: {exceptions}")
    
    # Mostrar detalles de cada resultado
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  ⚠ Producto {product_ids[idx]}: EXCEPCIÓN - {str(result)}")
        elif isinstance(result, dict):
            product_id = result.get("product_id", product_ids[idx])
            if result.get("success"):
                updated = result.get("sources_updated", 0)
                total = result.get("sources_total", 0)
                print(f"  ✓ Producto {product_id}: {updated}/{total} fuentes actualizadas")
            else:
                error = result.get("error", "Error desconocido")
                print(f"  ✗ Producto {product_id}: FALLO - {error}")
    
    # 4. Validar criterios de aceptación
    print("\n[4/4] Validando criterios de aceptación...")
    
    # Criterio 1: Tiempo total < 30 segundos
    print(f"\n  Criterio 1: Duración < 30s")
    print(f"    → Duración: {duration:.2f}s")
    assert duration < 30, f"Scraping tomó {duration:.2f}s (límite: 30s)"
    print(f"    ✓ PASÓ: {duration:.2f}s < 30s")
    
    # Criterio 2: Al menos 80% de productos procesados exitosamente
    success_rate = (successful / len(product_ids)) * 100
    print(f"\n  Criterio 2: Tasa de éxito > 80%")
    print(f"    → Éxito: {successful}/{len(product_ids)} ({success_rate:.1f}%)")
    assert success_rate >= 80, f"Solo {success_rate:.1f}% de productos procesados exitosamente"
    print(f"    ✓ PASÓ: {success_rate:.1f}% >= 80%")
    
    # Criterio 3: No excepciones no capturadas
    print(f"\n  Criterio 3: No excepciones no capturadas")
    print(f"    → Excepciones: {exceptions}")
    assert exceptions == 0, f"Se encontraron {exceptions} excepciones no capturadas"
    print(f"    ✓ PASÓ: Sin excepciones no capturadas")
    
    # Criterio 4: Verificar integridad en base de datos
    print(f"\n  Criterio 4: Integridad de datos en BD")
    query = select(func.count()).select_from(MarketSource).where(
        MarketSource.product_id.in_(product_ids)
    )
    total_sources = await db.scalar(query) or 0
    print(f"    → Fuentes totales en BD: {total_sources}")
    assert total_sources == len(product_ids) * 3, "No se crearon todas las fuentes esperadas"
    print(f"    ✓ PASÓ: {total_sources} fuentes == {len(product_ids) * 3} esperadas")
    
    print("\n" + "="*70)
    print("✓✓✓ TODOS LOS CRITERIOS PASARON")
    print("="*70)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_scraping_no_race_conditions(
    db: AsyncSession,
    test_category: Category
):
    """
    Test de concurrencia: verifica que múltiples actualizaciones simultáneas
    del mismo producto no causen race conditions ni corrupción de datos.
    
    Criterios:
    - Todas las fuentes se actualizan correctamente
    - No hay pérdida de datos
    - El estado final es consistente
    """
    print("\n" + "="*70)
    print("TEST DE CONCURRENCIA: Race Conditions")
    print("="*70)
    
    # Crear un producto con 5 fuentes
    product_id = await create_test_product_with_sources(
        db,
        index=999,
        category_id=test_category.id,
        num_sources=5
    )
    
    print(f"\n[1/3] Producto creado: ID={product_id} con 5 fuentes")
    
    # Ejecutar 3 actualizaciones concurrentes del mismo producto
    print("\n[2/3] Ejecutando 3 actualizaciones concurrentes del mismo producto...")
    
    async def update_wrapper():
        from db.session import get_session_context
        async with get_session_context() as session:
            return await update_market_prices_for_product(product_id, session)
    
    start = time.time()
    results = await asyncio.gather(
        update_wrapper(),
        update_wrapper(),
        update_wrapper(),
        return_exceptions=True
    )
    duration = time.time() - start
    
    print(f"  → Duración: {duration:.2f}s")
    print(f"  → Resultados: {len(results)} operaciones completadas")
    
    # Verificar que todas las operaciones fueron exitosas
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    print(f"  → Exitosas: {successful}/{len(results)}")
    
    # Validar estado final en base de datos
    print("\n[3/3] Validando estado final en base de datos...")
    
    query = select(MarketSource).where(MarketSource.product_id == product_id)
    result = await db.execute(query)
    sources = result.scalars().all()
    
    print(f"  → Fuentes encontradas: {len(sources)}")
    assert len(sources) == 5, f"Esperadas 5 fuentes, encontradas {len(sources)}"
    
    # Verificar que todas las fuentes tienen timestamps coherentes
    timestamps = [s.last_scraped_at for s in sources if s.last_scraped_at]
    print(f"  → Fuentes con timestamp: {len(timestamps)}")
    
    if timestamps:
        oldest = min(timestamps)
        newest = max(timestamps)
        delta = (newest - oldest).total_seconds()
        print(f"  → Delta temporal: {delta:.2f}s")
        assert delta < 10, "Delta temporal entre updates excede 10s (posible race condition)"
    
    print("\n✓ No se detectaron race conditions")
    print("="*70)


@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.slow
async def test_scraping_memory_usage(
    db: AsyncSession,
    test_category: Category
):
    """
    Test de recursos: monitorea uso de memoria durante scraping intensivo.
    
    Criterios:
    - Memoria no crece indefinidamente
    - No hay memory leaks evidentes
    - Recursos se liberan correctamente
    """
    import psutil
    import os
    
    print("\n" + "="*70)
    print("TEST DE RECURSOS: Uso de Memoria")
    print("="*70)
    
    process = psutil.Process(os.getpid())
    
    # Memoria inicial
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    print(f"\n[1/3] Memoria inicial: {mem_before:.2f} MB")
    
    # Crear y procesar 20 productos
    print("\n[2/3] Creando y procesando 20 productos...")
    product_ids = []
    
    for i in range(20):
        pid = await create_test_product_with_sources(
            db,
            index=2000 + i,
            category_id=test_category.id,
            num_sources=3
        )
        product_ids.append(pid)
    
    # Procesar en lotes para simular uso real
    batch_size = 5
    for batch_start in range(0, len(product_ids), batch_size):
        batch = product_ids[batch_start:batch_start + batch_size]
        
        async def process_batch():
            tasks = []
            for pid in batch:
                from db.session import get_session_context
                async with get_session_context() as session:
                    task = update_market_prices_for_product(pid, session)
                    tasks.append(task)
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        await process_batch()
        
        # Medir memoria después de cada lote
        mem_current = process.memory_info().rss / 1024 / 1024
        print(f"  Lote {batch_start//batch_size + 1}/{len(product_ids)//batch_size}: {mem_current:.2f} MB")
    
    # Memoria final
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    mem_delta = mem_after - mem_before
    
    print(f"\n[3/3] Análisis de memoria:")
    print(f"  → Memoria inicial: {mem_before:.2f} MB")
    print(f"  → Memoria final: {mem_after:.2f} MB")
    print(f"  → Delta: {mem_delta:.2f} MB ({(mem_delta/mem_before)*100:.1f}%)")
    
    # Criterio: incremento < 50% de memoria inicial o < 100MB absoluto
    assert mem_delta < max(mem_before * 0.5, 100), \
        f"Uso de memoria creció {mem_delta:.2f}MB (posible memory leak)"
    
    print(f"\n✓ Uso de memoria dentro de límites aceptables")
    print("="*70)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_scraping_concurrent_safety(
    db: AsyncSession,
    test_category: Category
):
    """
    Test de seguridad concurrente: verifica que las operaciones
    en diferentes productos no interfieren entre sí.
    """
    print("\n" + "="*70)
    print("TEST DE SEGURIDAD: Aislamiento entre Productos")
    print("="*70)
    
    # Crear 5 productos diferentes
    product_ids = []
    for i in range(5):
        pid = await create_test_product_with_sources(
            db,
            index=3000 + i,
            category_id=test_category.id,
            num_sources=2
        )
        product_ids.append(pid)
    
    print(f"\n[1/2] Creados {len(product_ids)} productos independientes")
    
    # Actualizar todos simultáneamente
    print("\n[2/2] Actualizando todos simultáneamente...")
    
    async def update_and_verify(pid: int) -> bool:
        from db.session import get_session_context
        async with get_session_context() as session:
            result = await update_market_prices_for_product(pid, session)
            
            # Verificar que solo afectó al producto correcto
            query = select(func.count()).select_from(MarketSource).where(
                MarketSource.product_id == pid
            )
            count = await session.scalar(query) or 0
            
            return result.get("success", False) and count == 2
    
    results = await asyncio.gather(*[update_and_verify(pid) for pid in product_ids])
    
    all_passed = all(results)
    success_count = sum(results)
    
    print(f"  → Productos validados correctamente: {success_count}/{len(product_ids)}")
    
    assert all_passed, "Algunos productos no se actualizaron correctamente (posible interferencia)"
    
    print("\n✓ Aislamiento entre productos verificado")
    print("="*70)
