#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_integration.py
# NG-HEADER: Ubicación: tests/test_market_integration.py
# NG-HEADER: Descripción: Tests de integración E2E para endpoints de actualización de Mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests de integración E2E para endpoints de Mercado.

Valida:
- PATCH /market/products/{id}/sale-price
- PATCH /market/products/{id}/market-reference
- POST /market/products/{id}/refresh-market
- Verificación de persistencia en BD
- Tests de seguridad (403)
- Mock de workers Dramatiq
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from unittest.mock import patch, Mock
from datetime import datetime

from db.models import CanonicalProduct, MarketSource, Category
from services.api import app
from services.auth import current_session, SessionData


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def db(db_session):
    """Sesión de DB para tests"""
    from db.session import SessionLocal
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client_collab(db_session):
    """Cliente HTTP con rol colaborador (permisos completos para Market)"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_no_perms(db_session):
    """Cliente HTTP sin permisos (rol 'cliente')"""
    # Override temporal del rol
    original_override = app.dependency_overrides.get(current_session)
    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "cliente")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    # Restaurar override original
    if original_override:
        app.dependency_overrides[current_session] = original_override
    else:
        app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")


@pytest_asyncio.fixture
async def product_with_sources(db: AsyncSession):
    """Helper: crea producto con fuentes de mercado"""
    async def _create(
        name: str = "Producto Test Market",
        ng_sku: str = "NGMARKET001",
        sale_price: float = 1000.00,
        market_price_reference: float | None = 900.00,
        sources_count: int = 2
    ):
        product = CanonicalProduct(
            name=name,
            ng_sku=ng_sku,
            sale_price=Decimal(str(sale_price)),
            market_price_reference=Decimal(str(market_price_reference)) if market_price_reference else None
        )
        db.add(product)
        await db.flush()
        
        sources = []
        for i in range(sources_count):
            source = MarketSource(
                product_id=product.id,
                url=f"https://example.com/product{i+1}",
                source_name=f"Fuente {i+1}",
                source_type="static",
                last_price=Decimal(str(850 + i * 50)),
                currency="ARS"
            )
            sources.append(source)
            db.add(source)
        
        await db.commit()
        await db.refresh(product)
        
        return product, sources
    
    return _create


# ==================== Tests PATCH /market/products/{id}/sale-price ====================

@pytest.mark.asyncio
async def test_update_sale_price_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualización exitosa de sale_price"""
    # Setup: crear producto
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST001",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Execute: actualizar precio
    payload = {"sale_price": 1500.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    # Assert: response correcta
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == product.id
    assert data["product_name"] == "Test Product"
    assert data["sale_price"] == 1500.00
    assert data["previous_price"] == 1000.00
    assert "updated_at" in data
    
    # Assert: persistencia en BD
    await db.refresh(product)
    assert product.sale_price == Decimal("1500.00")
    assert product.updated_at is not None


@pytest.mark.asyncio
async def test_update_sale_price_uses_custom_sku_as_name(client_collab: AsyncClient, db: AsyncSession):
    """Test: Usa sku_custom en el response si existe"""
    product = CanonicalProduct(
        name="Producto Original",
        ng_sku="TEST002",
        sku_custom="SKU-CUSTOM-002",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    payload = {"sale_price": 1200.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "SKU-CUSTOM-002"


@pytest.mark.asyncio
async def test_update_sale_price_product_not_found(client_collab: AsyncClient, db: AsyncSession):
    """Test: 404 cuando el producto no existe"""
    payload = {"sale_price": 1500.00}
    resp = await client_collab.patch(
        "/market/products/999999/sale-price",
        json=payload
    )
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_update_sale_price_negative_price(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando el precio es negativo"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST003",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"sale_price": -100.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sale_price_zero_price(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando el precio es cero (no permitido)"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST004",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"sale_price": 0.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sale_price_too_high(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando el precio excede el límite"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST005",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"sale_price": 1_000_000_000.00}  # > 999,999,999
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sale_price_forbidden_user(client_no_perms: AsyncClient, db: AsyncSession):
    """Test: 403 cuando el usuario no tiene permisos"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST006",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"sale_price": 1500.00}
    resp = await client_no_perms.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_sale_price_preserves_other_fields(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualización no modifica otros campos del producto"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TEST007",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00"),
        sku_custom="CUSTOM007"
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    original_market_price = product.market_price_reference
    original_custom_sku = product.sku_custom
    
    payload = {"sale_price": 1200.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 200
    
    await db.refresh(product)
    assert product.sale_price == Decimal("1200.00")
    assert product.market_price_reference == original_market_price
    assert product.sku_custom == original_custom_sku


# ==================== Tests PATCH /market/products/{id}/market-reference ====================

@pytest.mark.asyncio
async def test_update_market_reference_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualización exitosa de market_price_reference"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT001",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    payload = {"market_price_reference": 850.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == product.id
    assert data["product_name"] == "Test Product"
    assert data["market_price_reference"] == 850.00
    assert data["previous_market_price"] == 900.00
    assert "market_price_updated_at" in data
    
    # Verificar persistencia
    await db.refresh(product)
    assert product.market_price_reference == Decimal("850.00")
    assert product.market_price_updated_at is not None


@pytest.mark.asyncio
async def test_update_market_reference_zero_allowed(client_collab: AsyncClient, db: AsyncSession):
    """Test: Permite cero como valor válido (diferencia con sale_price)"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT002",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    payload = {"market_price_reference": 0.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_price_reference"] == 0.00
    
    await db.refresh(product)
    assert product.market_price_reference == Decimal("0.00")


@pytest.mark.asyncio
async def test_update_market_reference_from_null(client_collab: AsyncClient, db: AsyncSession):
    """Test: Puede establecer market_price_reference cuando es NULL"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT003",
        sale_price=Decimal("1000.00"),
        market_price_reference=None
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    payload = {"market_price_reference": 950.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_price_reference"] == 950.00
    assert data["previous_market_price"] is None
    
    await db.refresh(product)
    assert product.market_price_reference == Decimal("950.00")


@pytest.mark.asyncio
async def test_update_market_reference_not_found(client_collab: AsyncClient, db: AsyncSession):
    """Test: 404 cuando el producto no existe"""
    payload = {"market_price_reference": 850.00}
    resp = await client_collab.patch(
        "/market/products/999999/market-reference",
        json=payload
    )
    
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_market_reference_negative_price(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando el precio es negativo"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT004",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"market_price_reference": -50.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_market_reference_too_high(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando el precio excede el límite"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT005",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"market_price_reference": 1_000_000_000.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_market_reference_forbidden_user(client_no_perms: AsyncClient, db: AsyncSession):
    """Test: 403 cuando el usuario no tiene permisos"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT006",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00")
    )
    db.add(product)
    await db.commit()
    
    payload = {"market_price_reference": 850.00}
    resp = await client_no_perms.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_market_reference_updates_timestamp(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualiza market_price_updated_at correctamente"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTMKT007",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("900.00"),
        market_price_updated_at=None
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    assert product.market_price_updated_at is None
    
    payload = {"market_price_reference": 920.00}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 200
    
    await db.refresh(product)
    assert product.market_price_updated_at is not None
    assert isinstance(product.market_price_updated_at, datetime)


# ==================== Tests POST /market/products/{id}/refresh-market ====================

@pytest.mark.asyncio
@patch("workers.market_scraping.refresh_market_prices_task")
async def test_refresh_market_success(mock_task, client_collab: AsyncClient, db: AsyncSession):
    """Test: Encola tarea de scraping exitosamente"""
    # Setup
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTREF001",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Mock message con ID
    mock_message = Mock()
    mock_message.message_id = "test-job-abc123"
    mock_task.send.return_value = mock_message
    
    # Execute
    resp = await client_collab.post(f"/market/products/{product.id}/refresh-market")
    
    # Assert response
    assert resp.status_code == 202  # Accepted, no OK
    data = resp.json()
    assert data["status"] == "processing"  # Status real del endpoint
    assert data["product_id"] == product.id
    assert data["job_id"] == "test-job-abc123"
    assert "iniciada" in data["message"].lower()
    
    # Assert tarea llamada
    mock_task.send.assert_called_once_with(product.id)


@pytest.mark.asyncio
@patch("workers.market_scraping.refresh_market_prices_task")
async def test_refresh_market_not_found(mock_task, client_collab: AsyncClient, db: AsyncSession):
    """Test: 404 cuando el producto no existe"""
    resp = await client_collab.post("/market/products/999999/refresh-market")
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()
    
    # No debe llamar al worker
    mock_task.send.assert_not_called()


@pytest.mark.asyncio
@patch("workers.market_scraping.refresh_market_prices_task")
async def test_refresh_market_forbidden_user(mock_task, client_no_perms: AsyncClient, db: AsyncSession):
    """Test: 403 cuando el usuario no tiene permisos"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTREF002",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    resp = await client_no_perms.post(f"/market/products/{product.id}/refresh-market")
    
    assert resp.status_code == 403
    
    # No debe llamar al worker
    mock_task.send.assert_not_called()


@pytest.mark.asyncio
@patch("workers.market_scraping.refresh_market_prices_task")
async def test_refresh_market_worker_error(mock_task, client_collab: AsyncClient, db: AsyncSession):
    """Test: 500 cuando falla el encolado del worker"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTREF003",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    
    # Simular error en encolado
    mock_task.send.side_effect = Exception("Redis connection error")
    
    resp = await client_collab.post(f"/market/products/{product.id}/refresh-market")
    
    assert resp.status_code == 500  # Status real para errores generales
    data = resp.json()
    assert "error" in data["detail"].lower()


@pytest.mark.asyncio
@patch("workers.market_scraping.refresh_market_prices_task")
async def test_refresh_market_with_sources(
    mock_task,
    client_collab: AsyncClient,
    db: AsyncSession,
    product_with_sources
):
    """Test: Funciona correctamente con producto que tiene fuentes"""
    # Crear producto con fuentes
    product, sources = await product_with_sources(
        name="Producto con Fuentes",
        ng_sku="TESTREF004",
        sources_count=3
    )
    
    mock_message = Mock()
    mock_message.message_id = "job-with-sources-123"
    mock_task.send.return_value = mock_message
    
    resp = await client_collab.post(f"/market/products/{product.id}/refresh-market")
    
    assert resp.status_code == 202
    data = resp.json()
    assert data["product_id"] == product.id
    assert data["job_id"] == "job-with-sources-123"
    
    mock_task.send.assert_called_once_with(product.id)


# ==================== Tests de Casos Edge ====================

@pytest.mark.asyncio
async def test_sale_price_decimal_precision(client_collab: AsyncClient, db: AsyncSession):
    """Test: Maneja correctamente decimales con precisión"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTDEC001",
        sale_price=Decimal("1000.50")
    )
    db.add(product)
    await db.commit()
    
    payload = {"sale_price": 1234.99}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["sale_price"] == 1234.99
    
    await db.refresh(product)
    assert product.sale_price == Decimal("1234.99")


@pytest.mark.asyncio
async def test_market_reference_decimal_precision(client_collab: AsyncClient, db: AsyncSession):
    """Test: Maneja correctamente decimales en market_price_reference"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTDEC002",
        sale_price=Decimal("1000.00"),
        market_price_reference=Decimal("950.75")
    )
    db.add(product)
    await db.commit()
    
    payload = {"market_price_reference": 888.33}
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json=payload
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_price_reference"] == 888.33
    
    await db.refresh(product)
    assert product.market_price_reference == Decimal("888.33")


@pytest.mark.asyncio
async def test_concurrent_updates_sale_price(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualizaciones secuenciales de sale_price son consistentes"""
    product = CanonicalProduct(
        name="Test Product",
        ng_sku="TESTCONC001",
        sale_price=Decimal("1000.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Primera actualización
    resp1 = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": 1500.00}
    )
    assert resp1.status_code == 200
    
    await db.refresh(product)
    
    # Segunda actualización
    resp2 = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": 2000.00}
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["previous_price"] == 1500.00  # Debe reflejar el precio intermedio
    
    await db.refresh(product)
    assert product.sale_price == Decimal("2000.00")
