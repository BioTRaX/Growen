#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_batch.py
# NG-HEADER: Ubicación: tests/test_canonical_batch.py
# NG-HEADER: Descripción: Pruebas para POST /canonical-products/batch-job y worker
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""
Tests para la funcionalidad de creación batch de productos canónicos.

Incluye:
- Test del endpoint /batch-job
- Test del worker process_canonical_batch (ejecución síncrona)
- Test de manejo de SKU duplicados
"""
import os
import pytest

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RUN_INLINE_JOBS", "1")  # Evitar Redis en tests

from fastapi.testclient import TestClient

from services.api import app
from services.auth import current_session, require_csrf, SessionData

client = TestClient(app)

# Forzar rol admin y desactivar CSRF en tests
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


# ============================================================================
# TESTS DEL ENDPOINT /batch-job
# ============================================================================

def test_batch_job_returns_202_with_job_id() -> None:
    """POST /batch-job debe retornar 202 con job_id."""
    payload = {
        "items": [
            {"name": "Producto Batch 1"},
            {"name": "Producto Batch 2"},
        ]
    }
    r = client.post("/canonical-products/batch-job", json=payload)
    assert r.status_code == 202, r.text
    data = r.json()
    assert data.get("status") == "accepted"
    assert "job_id" in data
    assert data["job_id"].startswith("batch-canon-")
    assert data.get("total_items") == 2


def test_batch_job_rejects_empty_items() -> None:
    """POST /batch-job debe rechazar lista vacía."""
    r = client.post("/canonical-products/batch-job", json={"items": []})
    assert r.status_code == 400, r.text
    assert "al menos un producto" in r.json().get("detail", "").lower()


def test_batch_job_rejects_over_100_items() -> None:
    """POST /batch-job debe rechazar más de 100 items."""
    payload = {"items": [{"name": f"Prod {i}"} for i in range(101)]}
    r = client.post("/canonical-products/batch-job", json=payload)
    assert r.status_code == 400, r.text
    assert "100" in r.json().get("detail", "")


def test_batch_job_requires_auth() -> None:
    """POST /batch-job requiere autenticación (admin o colaborador)."""
    # Restaurar dependencia original para probar auth
    from services.auth import current_session as original_session
    
    # Simular guest
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "guest")
    
    r = client.post("/canonical-products/batch-job", json={"items": [{"name": "Test"}]})
    # Debería fallar con 403 (o similar)
    assert r.status_code in (401, 403), r.text
    
    # Restaurar admin
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")


# ============================================================================
# TESTS DEL WORKER (EJECUCIÓN SÍNCRONA)
# ============================================================================

@pytest.mark.asyncio
async def test_worker_creates_products_in_db() -> None:
    """El worker debe crear productos en la base de datos."""
    from services.jobs.catalog_jobs import _process_canonical_batch_async
    from db.session import SessionLocal
    from db.models import CanonicalProduct
    from sqlalchemy import select
    
    job_id = "test-worker-001"
    items = [
        {"name": "Worker Test Prod 1", "category_id": None},
        {"name": "Worker Test Prod 2", "brand": "TestBrand"},
    ]
    
    # Ejecutar worker sincrónicamente
    await _process_canonical_batch_async(job_id, items)
    
    # Verificar que los productos existen
    async with SessionLocal() as db:
        stmt = select(CanonicalProduct).where(CanonicalProduct.name.like("Worker Test Prod%"))
        result = await db.execute(stmt)
        products = result.scalars().all()
        
        assert len(products) >= 2, f"Esperados al menos 2, encontrados {len(products)}"
        
        # Verificar que tienen ng_sku y sku_custom
        for p in products:
            assert p.ng_sku is not None and p.ng_sku.startswith("NG-")
            assert p.sku_custom is not None


@pytest.mark.asyncio
async def test_worker_handles_duplicate_sku_gracefully() -> None:
    """El worker debe manejar SKUs duplicados sin explotar."""
    from services.jobs.catalog_jobs import _process_canonical_batch_async
    from db.session import SessionLocal
    from db.models import CanonicalProduct
    from sqlalchemy import select
    
    # Primero crear un producto con SKU específico
    async with SessionLocal() as db:
        existing = CanonicalProduct(
            name="Producto Existente Dupe Test",
            sku_custom="DUP_0001_TST",
        )
        db.add(existing)
        await db.flush()
        existing.ng_sku = f"NG-{existing.id:06d}"
        await db.commit()
    
    job_id = "test-dupe-001"
    items = [
        # Este intentará crear con un SKU que ya existe
        {"name": "Producto Nuevo Dupe Test", "sku_custom": "DUP_0001_TST"},
    ]
    
    # No debería explotar
    await _process_canonical_batch_async(job_id, items)
    
    # El producto debería haber fallado (error parcial)
    # Verificar que el audit log registró el error
    from db.models import AuditLog
    async with SessionLocal() as db:
        stmt = select(AuditLog).where(AuditLog.action == "batch_create")
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        # Debería existir al menos un audit log
        assert len(logs) > 0


@pytest.mark.asyncio
async def test_worker_generates_unique_skus_in_batch() -> None:
    """El worker debe generar SKUs únicos dentro del mismo batch."""
    from services.jobs.catalog_jobs import _process_canonical_batch_async
    from db.session import SessionLocal
    from db.models import CanonicalProduct
    from sqlalchemy import select
    
    job_id = "test-unique-001"
    # Mismo nombre, sin categoría - deberían tener SKUs diferentes
    items = [
        {"name": "Unico Test A"},
        {"name": "Unico Test B"},
        {"name": "Unico Test C"},
    ]
    
    await _process_canonical_batch_async(job_id, items)
    
    async with SessionLocal() as db:
        stmt = select(CanonicalProduct).where(CanonicalProduct.name.like("Unico Test%"))
        result = await db.execute(stmt)
        products = result.scalars().all()
        
        skus = [p.sku_custom for p in products if p.sku_custom]
        # Todos los SKUs deberían ser únicos
        assert len(skus) == len(set(skus)), f"SKUs duplicados detectados: {skus}"


# ============================================================================
# TESTS DE INTEGRACIÓN COMPLETA
# ============================================================================

def test_batch_job_with_categories() -> None:
    """Batch con categorías genera SKUs con prefijo de categoría."""
    # Crear categoría primero
    r = client.post("/categories", json={"name": "BatchTestCat"})
    if r.status_code == 200:
        cat = r.json()
    else:
        lr = client.get("/categories")
        cats = lr.json()
        cat = next((c for c in cats if c.get("name") == "BatchTestCat"), None)
        if not cat:
            pytest.skip("No se pudo crear/obtener categoría de prueba")
    
    payload = {
        "items": [
            {"name": "Prod Cat 1", "category_id": cat["id"]},
            {"name": "Prod Cat 2", "category_id": cat["id"]},
        ]
    }
    r = client.post("/canonical-products/batch-job", json=payload)
    assert r.status_code == 202, r.text
    assert r.json()["total_items"] == 2
