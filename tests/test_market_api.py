#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_market_api.py
# NG-HEADER: Ubicación: tests/test_market_api.py
# NG-HEADER: Descripción: Tests para endpoints del módulo Mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Tests para el módulo Mercado (Market).

Valida:
- Endpoint GET /market/products
- Filtros por nombre, categoría, proveedor
- Paginación
- Control de acceso por roles
- Formato de respuesta
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CanonicalProduct, Category, ProductEquivalence, Supplier, SupplierProduct, User, MarketSource
from services.api import app


@pytest.mark.asyncio
async def test_market_products_list_empty(client_collab: AsyncClient):
    """Test: Lista vacía cuando no hay productos"""
    resp = await client_collab.get("/market/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0


@pytest.mark.asyncio
async def test_market_products_list_basic(client_collab: AsyncClient, db: AsyncSession):
    """Test: Lista básica de productos"""
    # Crear categoría
    cat = Category(name="Electrónica", parent_id=None)
    db.add(cat)
    await db.flush()
    
    # Crear productos canónicos
    p1 = CanonicalProduct(
        name="Producto A",
        ng_sku="NG001",
        sale_price=1500.00,
        market_price_reference=1200.00,
        category_id=cat.id,
    )
    p2 = CanonicalProduct(
        name="Producto B",
        ng_sku="NG002",
        sale_price=2500.00,
        category_id=cat.id,
    )
    db.add_all([p1, p2])
    await db.commit()
    
    resp = await client_collab.get("/market/products")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["pages"] == 1
    
    # Verificar orden alfabético
    assert data["items"][0]["preferred_name"] == "Producto A"
    assert data["items"][1]["preferred_name"] == "Producto B"
    
    # Verificar campos
    item_a = data["items"][0]
    assert item_a["product_id"] == p1.id
    assert item_a["sale_price"] == 1500.00
    assert item_a["market_price_reference"] == 1200.00
    assert item_a["category_name"] == "Electrónica"
    
    item_b = data["items"][1]
    assert item_b["sale_price"] == 2500.00
    assert item_b["market_price_reference"] is None


@pytest.mark.asyncio
async def test_market_products_filter_by_name(client_collab: AsyncClient, db: AsyncSession):
    """Test: Filtrar productos por nombre"""
    p1 = CanonicalProduct(name="Cámara Digital", ng_sku="NG001", sale_price=5000.00)
    p2 = CanonicalProduct(name="Teléfono Móvil", ng_sku="NG002", sale_price=3000.00)
    p3 = CanonicalProduct(name="Cámara Web", ng_sku="NG003", sale_price=800.00)
    db.add_all([p1, p2, p3])
    await db.commit()
    
    # Buscar por "cámara" (case-insensitive)
    resp = await client_collab.get("/market/products?q=cámara")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 2
    assert len(data["items"]) == 2
    names = {item["preferred_name"] for item in data["items"]}
    assert "Cámara Digital" in names
    assert "Cámara Web" in names
    assert "Teléfono Móvil" not in names


@pytest.mark.asyncio
async def test_market_products_filter_by_category(client_collab: AsyncClient, db: AsyncSession):
    """Test: Filtrar productos por categoría"""
    cat1 = Category(name="Tecnología", parent_id=None)
    cat2 = Category(name="Hogar", parent_id=None)
    db.add_all([cat1, cat2])
    await db.flush()
    
    p1 = CanonicalProduct(name="Laptop", ng_sku="NG001", category_id=cat1.id)
    p2 = CanonicalProduct(name="Mouse", ng_sku="NG002", category_id=cat1.id)
    p3 = CanonicalProduct(name="Lámpara", ng_sku="NG003", category_id=cat2.id)
    db.add_all([p1, p2, p3])
    await db.commit()
    
    # Filtrar por categoría Tecnología
    resp = await client_collab.get(f"/market/products?category_id={cat1.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 2
    names = {item["preferred_name"] for item in data["items"]}
    assert "Laptop" in names
    assert "Mouse" in names
    assert "Lámpara" not in names


@pytest.mark.asyncio
async def test_market_products_filter_by_supplier(client_collab: AsyncClient, db: AsyncSession):
    """Test: Filtrar productos por proveedor"""
    # Crear proveedores
    sup1 = Supplier(name="Proveedor A", slug="prov-a")
    sup2 = Supplier(name="Proveedor B", slug="prov-b")
    db.add_all([sup1, sup2])
    await db.flush()
    
    # Crear productos canónicos
    p1 = CanonicalProduct(name="Producto 1", ng_sku="NG001")
    p2 = CanonicalProduct(name="Producto 2", ng_sku="NG002")
    p3 = CanonicalProduct(name="Producto 3", ng_sku="NG003")
    db.add_all([p1, p2, p3])
    await db.flush()
    
    # Crear productos de proveedor
    sp1 = SupplierProduct(
        supplier_id=sup1.id,
        supplier_product_id="SP001",
        title="Item 1",
        internal_product_id=p1.id,
    )
    sp2 = SupplierProduct(
        supplier_id=sup1.id,
        supplier_product_id="SP002",
        title="Item 2",
        internal_product_id=p2.id,
    )
    sp3 = SupplierProduct(
        supplier_id=sup2.id,
        supplier_product_id="SP003",
        title="Item 3",
        internal_product_id=p3.id,
    )
    db.add_all([sp1, sp2, sp3])
    await db.flush()
    
    # Crear equivalencias
    eq1 = ProductEquivalence(
        supplier_id=sup1.id,
        supplier_product_id=sp1.id,
        canonical_product_id=p1.id,
        source="manual",  # Campo obligatorio
    )
    eq2 = ProductEquivalence(
        supplier_id=sup1.id,
        supplier_product_id=sp2.id,
        canonical_product_id=p2.id,
        source="manual",
    )
    eq3 = ProductEquivalence(
        supplier_id=sup2.id,
        supplier_product_id=sp3.id,
        canonical_product_id=p3.id,
        source="manual",
    )
    db.add_all([eq1, eq2, eq3])
    await db.commit()
    
    # Filtrar por Proveedor A
    resp = await client_collab.get(f"/market/products?supplier_id={sup1.id}")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 2
    names = {item["preferred_name"] for item in data["items"]}
    assert "Producto 1" in names
    assert "Producto 2" in names
    assert "Producto 3" not in names


@pytest.mark.asyncio
async def test_market_products_pagination(client_collab: AsyncClient, db: AsyncSession):
    """Test: Paginación de resultados"""
    # Crear 10 productos
    products = [
        CanonicalProduct(name=f"Producto {chr(65+i)}", ng_sku=f"NG{i:03d}")
        for i in range(10)
    ]
    db.add_all(products)
    await db.commit()
    
    # Página 1 (5 items)
    resp = await client_collab.get("/market/products?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 10
    assert len(data["items"]) == 5
    assert data["page"] == 1
    assert data["pages"] == 2
    assert data["page_size"] == 5
    
    # Página 2 (5 items restantes)
    resp = await client_collab.get("/market/products?page=2&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 10
    assert len(data["items"]) == 5
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_market_products_combined_filters(client_collab: AsyncClient, db: AsyncSession):
    """Test: Combinación de múltiples filtros"""
    cat = Category(name="Gaming", parent_id=None)
    db.add(cat)
    await db.flush()
    
    p1 = CanonicalProduct(name="Teclado Gamer", ng_sku="NG001", category_id=cat.id)
    p2 = CanonicalProduct(name="Mouse Gamer", ng_sku="NG002", category_id=cat.id)
    p3 = CanonicalProduct(name="Audífonos Gamer", ng_sku="NG003", category_id=cat.id)
    p4 = CanonicalProduct(name="Monitor", ng_sku="NG004")  # Sin categoría
    db.add_all([p1, p2, p3, p4])
    await db.commit()
    
    # Filtrar por categoría + búsqueda "gamer"
    resp = await client_collab.get(f"/market/products?category_id={cat.id}&q=mouse")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 1
    assert data["items"][0]["preferred_name"] == "Mouse Gamer"


@pytest.mark.asyncio
@pytest.mark.no_auth_override
async def test_market_products_requires_auth(client: AsyncClient):
    """Test: Requiere autenticación"""
    resp = await client.get("/market/products")
    assert resp.status_code in [401, 403]


@pytest.mark.asyncio
@pytest.mark.no_auth_override
async def test_market_products_requires_collab_or_admin(client_viewer: AsyncClient):
    """Test: Rol viewer no tiene acceso"""
    # Asumiendo que client_viewer es un fixture con rol 'viewer'
    # Si no existe, este test puede ser ajustado
    resp = await client_viewer.get("/market/products")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_market_products_preferred_name_custom_sku(client_collab: AsyncClient, db: AsyncSession):
    """Test: preferred_name usa sku_custom si existe"""
    p1 = CanonicalProduct(
        name="Producto Original",
        ng_sku="NG001",
        sku_custom="CUSTOM_SKU_001",
        sale_price=1000.00,
    )
    p2 = CanonicalProduct(
        name="Producto Sin Custom",
        ng_sku="NG002",
        sale_price=2000.00,
    )
    db.add_all([p1, p2])
    await db.commit()
    
    resp = await client_collab.get("/market/products")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total"] == 2
    
    # p1 debe usar sku_custom como preferred_name
    item_custom = next(item for item in data["items"] if item["product_id"] == p1.id)
    assert item_custom["preferred_name"] == "CUSTOM_SKU_001"
    
    # p2 debe usar name como preferred_name
    item_normal = next(item for item in data["items"] if item["product_id"] == p2.id)
    assert item_normal["preferred_name"] == "Producto Sin Custom"


@pytest.mark.asyncio
async def test_market_products_schema_fields(client_collab: AsyncClient, db: AsyncSession):
    """Test: Todos los campos del schema están presentes"""
    from datetime import datetime, timedelta
    from decimal import Decimal
    
    cat = Category(name="Test", parent_id=None)
    db.add(cat)
    await db.flush()
    
    # Crear producto con market_price_updated_at
    past_date = datetime.utcnow() - timedelta(days=5)
    p = CanonicalProduct(
        name="Test Product",
        ng_sku="NG001",
        sale_price=Decimal("1500.50"),
        market_price_reference=Decimal("1300.75"),
        market_price_updated_at=past_date,
        category_id=cat.id,
    )
    db.add(p)
    await db.commit()
    
    resp = await client_collab.get("/market/products")
    assert resp.status_code == 200
    data = resp.json()
    
    item = data["items"][0]
    
    # Verificar todos los campos esperados
    assert "product_id" in item
    assert "preferred_name" in item
    assert "sale_price" in item
    assert "market_price_reference" in item
    assert "market_price_min" in item
    assert "market_price_max" in item
    assert "last_market_update" in item
    assert "category_id" in item
    assert "category_name" in item
    assert "supplier_id" in item
    assert "supplier_name" in item
    
    # Verificar valores
    assert item["sale_price"] == 1500.50
    assert item["market_price_reference"] == 1300.75
    assert item["category_name"] == "Test"
    
    # Verificar que last_market_update usa market_price_updated_at
    assert item["last_market_update"] is not None
    assert item["last_market_update"] == past_date.isoformat()
    
    # Campos pendientes de Etapa 2 deben ser None
    assert item["market_price_min"] is None
    assert item["market_price_max"] is None


# Fixtures necesarias (si no existen en conftest.py)
@pytest_asyncio.fixture
async def db(db_session):
    """Sesión de DB para tests"""
    from db.session import SessionLocal
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Cliente HTTP sin autenticación"""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_collab(db_session):
    """Cliente HTTP con rol colaborador"""
    # TODO: Implementar fixture con sesión de colaborador
    # Por ahora, mock básico
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Agregar headers de autenticación si es necesario
        yield ac


@pytest_asyncio.fixture
async def client_viewer(db_session):
    """Cliente HTTP con rol viewer"""
    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ==================== Tests GET /products/{id}/sources ====================

@pytest.mark.asyncio
async def test_get_product_sources_not_found(client_collab: AsyncClient):
    """Test: 404 cuando el producto no existe"""
    resp = await client_collab.get("/market/products/999999/sources")
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_product_sources_empty(client_collab: AsyncClient, db: AsyncSession):
    """Test: Producto sin fuentes retorna listas vacías"""
    # Crear producto sin fuentes
    product = CanonicalProduct(name="Producto Sin Fuentes", ng_sku="NG999")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.get(f"/market/products/{product.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["product_id"] == product.id
    assert data["product_name"] == "Producto Sin Fuentes"
    assert data["mandatory"] == []
    assert data["additional"] == []
    assert data["sale_price"] is None
    assert data["market_price_reference"] is None


@pytest.mark.asyncio
async def test_get_product_sources_with_data(client_collab: AsyncClient, db: AsyncSession):
    """Test: Producto con fuentes obligatorias y adicionales"""
    from decimal import Decimal
    from datetime import datetime, timedelta
    
    # Crear producto
    product = CanonicalProduct(
        name="Producto Con Fuentes",
        ng_sku="NG123",
        sale_price=Decimal("1500.00"),
        market_price_reference=Decimal("1400.00")
    )
    db.add(product)
    await db.flush()
    
    # Crear fuentes obligatorias
    source1 = MarketSource(
        product_id=product.id,
        source_name="MercadoLibre",
        url="https://www.mercadolibre.com.ar/producto",
        last_price=Decimal("1350.00"),
        last_checked_at=datetime.utcnow() - timedelta(hours=2),
        is_mandatory=True
    )
    
    source2 = MarketSource(
        product_id=product.id,
        source_name="SantaPlanta",
        url="https://www.santaplanta.com.ar/producto",
        last_price=Decimal("1420.00"),
        last_checked_at=datetime.utcnow() - timedelta(days=1),
        is_mandatory=True
    )
    
    # Crear fuente adicional
    source3 = MarketSource(
        product_id=product.id,
        source_name="Tienda Online",
        url="https://www.ejemplo.com/producto",
        last_price=None,
        last_checked_at=None,
        is_mandatory=False
    )
    
    db.add_all([source1, source2, source3])
    await db.commit()
    
    resp = await client_collab.get(f"/market/products/{product.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    
    # Validar estructura básica
    assert data["product_id"] == product.id
    assert data["product_name"] == "Producto Con Fuentes"
    assert data["sale_price"] == 1500.0
    assert data["market_price_reference"] == 1400.0
    
    # Validar fuentes obligatorias (2)
    assert len(data["mandatory"]) == 2
    assert all(src["is_mandatory"] for src in data["mandatory"])
    
    # Validar fuentes adicionales (1)
    assert len(data["additional"]) == 1
    assert not data["additional"][0]["is_mandatory"]
    
    # Validar campos de la primera fuente obligatoria
    ml_source = next((s for s in data["mandatory"] if s["source_name"] == "MercadoLibre"), None)
    assert ml_source is not None
    assert ml_source["url"] == "https://www.mercadolibre.com.ar/producto"
    assert ml_source["last_price"] == 1350.0
    assert ml_source["last_checked_at"] is not None
    
    # Validar fuente adicional sin precio
    additional = data["additional"][0]
    assert additional["source_name"] == "Tienda Online"
    assert additional["last_price"] is None
    assert additional["last_checked_at"] is None


@pytest.mark.asyncio
async def test_get_product_sources_preferred_name(client_collab: AsyncClient, db: AsyncSession):
    """Test: Usa sku_custom como preferred_name si existe"""
    product = CanonicalProduct(
        name="Nombre Original",
        sku_custom="CUSTOM_001",
        ng_sku="NG456"
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.get(f"/market/products/{product.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    
    # Debe usar sku_custom como product_name
    assert data["product_name"] == "CUSTOM_001"


@pytest.mark.asyncio
async def test_get_product_sources_fields_validation(client_collab: AsyncClient, db: AsyncSession):
    """Test: Validar que todos los campos requeridos estén presentes"""
    from datetime import datetime
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG789")
    db.add(product)
    await db.flush()
    
    source = MarketSource(
        product_id=product.id,
        source_name="Test Source",
        url="https://test.com/product",
        last_price=Decimal("100.00"),
        last_checked_at=datetime.utcnow(),
        is_mandatory=True
    )
    db.add(source)
    await db.commit()
    
    resp = await client_collab.get(f"/market/products/{product.id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    
    # Validar campos de nivel producto
    assert "product_id" in data
    assert "product_name" in data
    assert "sale_price" in data
    assert "market_price_reference" in data
    assert "mandatory" in data
    assert "additional" in data
    
    # Validar campos de fuente
    source_item = data["mandatory"][0]
    assert "id" in source_item
    assert "source_name" in source_item
    assert "url" in source_item
    assert "last_price" in source_item
    assert "last_checked_at" in source_item
    assert "is_mandatory" in source_item
    assert "created_at" in source_item
    assert "updated_at" in source_item


@pytest.mark.asyncio
async def test_get_sources_includes_market_price_updated_at(client_collab: AsyncClient, db: AsyncSession):
    """Test: GET /products/{id}/sources incluye market_price_updated_at"""
    from datetime import datetime, timedelta
    from decimal import Decimal
    
    # Crear producto con market_price_updated_at
    past_date = datetime.utcnow() - timedelta(days=3)
    product = CanonicalProduct(
        name="Producto Con Actualización",
        ng_sku="NG501",
        market_price_reference=Decimal("1500.00"),
        market_price_updated_at=past_date
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Obtener fuentes del producto
    resp = await client_collab.get(f"/market/products/{product.id}/sources")
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Verificar que market_price_updated_at está presente
    assert "market_price_updated_at" in data
    assert data["market_price_updated_at"] is not None
    assert data["market_price_updated_at"] == past_date.isoformat()


# ==================== Tests PATCH /products/{id}/sale-price ====================

@pytest.mark.asyncio
async def test_update_sale_price_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualización exitosa de precio de venta"""
    from decimal import Decimal
    
    # Crear producto con precio inicial
    product = CanonicalProduct(
        name="Producto Test",
        ng_sku="NG001",
        sale_price=Decimal("100.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Actualizar precio
    new_price = 150.00
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": new_price}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Validar respuesta
    assert data["product_id"] == product.id
    assert data["sale_price"] == new_price
    assert data["previous_price"] == 100.0
    assert "updated_at" in data
    
    # Verificar que se guardó en DB
    await db.refresh(product)
    assert float(product.sale_price) == new_price


@pytest.mark.asyncio
async def test_update_sale_price_negative_rejected(client_collab: AsyncClient, db: AsyncSession):
    """Test: Rechaza precio negativo"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG002", sale_price=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": -50.00}
    )
    
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_update_sale_price_zero_rejected(client_collab: AsyncClient, db: AsyncSession):
    """Test: Rechaza precio cero"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG003", sale_price=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": 0}
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sale_price_product_not_found(client_collab: AsyncClient):
    """Test: 404 cuando producto no existe"""
    resp = await client_collab.patch(
        "/market/products/999999/sale-price",
        json={"sale_price": 100.00}
    )
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_update_sale_price_invalid_type(client_collab: AsyncClient, db: AsyncSession):
    """Test: Rechaza tipo inválido (string)"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG004", sale_price=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": "not a number"}
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_sale_price_from_null(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualizar precio cuando antes era NULL"""
    product = CanonicalProduct(name="Test Product", ng_sku="NG005", sale_price=None)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": 200.00}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["sale_price"] == 200.0
    assert data["previous_price"] is None


@pytest.mark.asyncio
async def test_update_sale_price_preferred_name(client_collab: AsyncClient, db: AsyncSession):
    """Test: Usa sku_custom en respuesta si existe"""
    from decimal import Decimal
    
    product = CanonicalProduct(
        name="Nombre Original",
        sku_custom="CUSTOM_SKU_001",
        ng_sku="NG006",
        sale_price=Decimal("100.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/sale-price",
        json={"sale_price": 150.00}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "CUSTOM_SKU_001"


# ==================== Tests PATCH /products/{id}/market-reference ====================

@pytest.mark.asyncio
async def test_update_market_reference_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualización exitosa de precio de mercado de referencia"""
    from decimal import Decimal
    
    # Crear producto con precio de mercado inicial
    product = CanonicalProduct(
        name="Producto Test",
        ng_sku="NG101",
        market_price_reference=Decimal("200.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Actualizar precio de mercado
    new_price = 250.00
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": new_price}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    
    # Validar respuesta
    assert data["product_id"] == product.id
    assert data["market_price_reference"] == new_price
    assert data["previous_market_price"] == 200.0
    assert "market_price_updated_at" in data
    
    # Verificar que se guardó en DB
    await db.refresh(product)
    assert float(product.market_price_reference) == new_price
    assert product.market_price_updated_at is not None


@pytest.mark.asyncio
async def test_update_market_reference_negative_rejected(client_collab: AsyncClient, db: AsyncSession):
    """Test: Rechaza precio negativo"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG102", market_price_reference=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": -50.00}
    )
    
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_update_market_reference_zero_allowed(client_collab: AsyncClient, db: AsyncSession):
    """Test: Acepta precio cero (válido para market_price_reference)"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG103", market_price_reference=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": 0.0}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_price_reference"] == 0.0


@pytest.mark.asyncio
async def test_update_market_reference_product_not_found(client_collab: AsyncClient):
    """Test: 404 cuando producto no existe"""
    resp = await client_collab.patch(
        "/market/products/999999/market-reference",
        json={"market_price_reference": 100.00}
    )
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_update_market_reference_invalid_type(client_collab: AsyncClient, db: AsyncSession):
    """Test: Rechaza tipo inválido (string)"""
    from decimal import Decimal
    
    product = CanonicalProduct(name="Test Product", ng_sku="NG104", market_price_reference=Decimal("100.00"))
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": "not a number"}
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_market_reference_from_null(client_collab: AsyncClient, db: AsyncSession):
    """Test: Actualizar precio cuando antes era NULL"""
    product = CanonicalProduct(name="Test Product", ng_sku="NG105", market_price_reference=None)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": 300.00}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["market_price_reference"] == 300.0
    assert data["previous_market_price"] is None
    assert "market_price_updated_at" in data


@pytest.mark.asyncio
async def test_update_market_reference_preferred_name(client_collab: AsyncClient, db: AsyncSession):
    """Test: Usa sku_custom en respuesta si existe"""
    from decimal import Decimal
    
    product = CanonicalProduct(
        name="Nombre Original",
        sku_custom="CUSTOM_SKU_002",
        ng_sku="NG106",
        market_price_reference=Decimal("100.00")
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    resp = await client_collab.patch(
        f"/market/products/{product.id}/market-reference",
        json={"market_price_reference": 150.00}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "CUSTOM_SKU_002"


# ==================== Tests POST /products/{id}/refresh-market ====================

@pytest.mark.asyncio
async def test_refresh_market_prices_success(client_collab: AsyncClient, db: AsyncSession, monkeypatch):
    """Test: Encolado exitoso de tarea de scraping"""
    from decimal import Decimal
    
    # Crear producto con fuentes
    product = CanonicalProduct(name="Producto Test", ng_sku="NG201")
    db.add(product)
    await db.flush()
    
    source1 = MarketSource(
        product_id=product.id,
        source_name="MercadoLibre",
        url="https://mercadolibre.com/test",
        is_mandatory=True
    )
    source2 = MarketSource(
        product_id=product.id,
        source_name="Amazon",
        url="https://amazon.com/test",
        is_mandatory=False
    )
    db.add_all([source1, source2])
    await db.commit()
    await db.refresh(product)
    
    # Mock de la tarea de Dramatiq para evitar ejecución real
    class MockMessage:
        message_id = "test-job-123"
    
    def mock_send(product_id):
        return MockMessage()
    
    # Patchear la tarea del worker
    import workers.market_scraping
    monkeypatch.setattr(workers.market_scraping.refresh_market_prices_task, 'send', mock_send)
    
    # Ejecutar endpoint
    resp = await client_collab.post(f"/market/products/{product.id}/refresh-market")
    
    assert resp.status_code == 202
    data = resp.json()
    
    # Validar respuesta
    assert data["status"] == "processing"
    assert data["product_id"] == product.id
    assert "actualización" in data["message"].lower()
    assert "job_id" in data  # Puede ser None o string


@pytest.mark.asyncio
async def test_refresh_market_prices_product_not_found(client_collab: AsyncClient):
    """Test: 404 cuando producto no existe"""
    resp = await client_collab.post("/market/products/999999/refresh-market")
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_market_prices_no_sources(client_collab: AsyncClient, db: AsyncSession, monkeypatch):
    """Test: Acepta producto sin fuentes (encolará pero worker reportará 0 fuentes)"""
    # Crear producto sin fuentes
    product = CanonicalProduct(name="Producto Sin Fuentes", ng_sku="NG202")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Mock de la tarea
    class MockMessage:
        message_id = "test-job-456"
    
    def mock_send(product_id):
        return MockMessage()
    
    import workers.market_scraping
    monkeypatch.setattr(workers.market_scraping.refresh_market_prices_task, 'send', mock_send)
    
    # Ejecutar endpoint (debe aceptar aunque no tenga fuentes)
    resp = await client_collab.post(f"/market/products/{product.id}/refresh-market")
    
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "processing"
    assert data["product_id"] == product.id


# ==================== Tests POST /products/{id}/sources ====================

@pytest.mark.asyncio
async def test_add_source_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Agregar fuente exitosamente"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG301")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Agregar fuente
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "MercadoLibre",
            "url": "https://mercadolibre.com.ar/producto-test",
            "is_mandatory": True
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    
    # Validar respuesta
    assert data["product_id"] == product.id
    assert data["source_name"] == "MercadoLibre"
    assert data["url"] == "https://mercadolibre.com.ar/producto-test"
    assert data["is_mandatory"] is True
    assert data["last_price"] is None
    assert data["last_checked_at"] is None
    assert "created_at" in data
    assert "id" in data
    
    # Verificar que se guardó en DB
    await db.refresh(product)
    query = select(MarketSource).where(MarketSource.product_id == product.id)
    result = await db.execute(query)
    sources = result.scalars().all()
    assert len(sources) == 1
    assert sources[0].source_name == "MercadoLibre"


@pytest.mark.asyncio
async def test_add_source_product_not_found(client_collab: AsyncClient):
    """Test: 404 cuando producto no existe"""
    resp = await client_collab.post(
        "/market/products/999999/sources",
        json={
            "source_name": "Test",
            "url": "https://example.com/test",
            "is_mandatory": False
        }
    )
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrado" in data["detail"].lower()


@pytest.mark.asyncio
async def test_add_source_duplicate_url(client_collab: AsyncClient, db: AsyncSession):
    """Test: 409 cuando URL ya existe para el producto"""
    # Crear producto con fuente existente
    product = CanonicalProduct(name="Producto Test", ng_sku="NG302")
    db.add(product)
    await db.flush()
    
    existing_source = MarketSource(
        product_id=product.id,
        source_name="Fuente Existente",
        url="https://example.com/duplicate",
        is_mandatory=False
    )
    db.add(existing_source)
    await db.commit()
    await db.refresh(product)
    
    # Intentar agregar fuente con misma URL
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Nueva Fuente",
            "url": "https://example.com/duplicate",
            "is_mandatory": True
        }
    )
    
    assert resp.status_code == 409
    data = resp.json()
    assert "ya existe" in data["detail"].lower()


@pytest.mark.asyncio
async def test_add_source_invalid_url(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando URL es inválida"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG303")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Intentar agregar fuente con URL inválida (sin esquema)
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Fuente Inválida",
            "url": "not-a-valid-url",
            "is_mandatory": False
        }
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_source_url_without_scheme(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando URL no tiene esquema http/https"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG304")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Intentar agregar fuente con URL sin esquema
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Fuente Sin Esquema",
            "url": "example.com/test",
            "is_mandatory": False
        }
    )
    
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_source_optional_mandatory_false(client_collab: AsyncClient, db: AsyncSession):
    """Test: is_mandatory es opcional (default False)"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG305")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Agregar fuente sin especificar is_mandatory
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Fuente Opcional",
            "url": "https://example.com/optional"
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_mandatory"] is False


@pytest.mark.asyncio
async def test_add_source_with_currency_and_type(client_collab: AsyncClient, db: AsyncSession):
    """Test: Agregar fuente con moneda y tipo especificados"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG306")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Agregar fuente con currency y source_type
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Amazon US",
            "url": "https://amazon.com/product-xyz",
            "currency": "USD",
            "source_type": "dynamic",
            "is_mandatory": True
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["currency"] == "USD"
    assert data["source_type"] == "dynamic"
    assert data["is_mandatory"] is True


@pytest.mark.asyncio
async def test_add_source_invalid_source_type(client_collab: AsyncClient, db: AsyncSession):
    """Test: 422 cuando source_type es inválido"""
    # Crear producto
    product = CanonicalProduct(name="Producto Test", ng_sku="NG307")
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    # Intentar agregar fuente con source_type inválido
    resp = await client_collab.post(
        f"/market/products/{product.id}/sources",
        json={
            "source_name": "Fuente Inválida",
            "url": "https://example.com/test",
            "source_type": "invalid_type"
        }
    )
    
    assert resp.status_code == 422


# ==================== Tests DELETE /sources/{source_id} ====================

@pytest.mark.asyncio
async def test_delete_source_success(client_collab: AsyncClient, db: AsyncSession):
    """Test: Eliminar fuente exitosamente"""
    # Crear producto con fuente
    product = CanonicalProduct(name="Producto Test", ng_sku="NG401")
    db.add(product)
    await db.flush()
    
    source = MarketSource(
        product_id=product.id,
        source_name="Fuente a Eliminar",
        url="https://example.com/delete-me",
        is_mandatory=False
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    
    source_id = source.id
    
    # Eliminar fuente
    resp = await client_collab.delete(f"/market/sources/{source_id}")
    
    assert resp.status_code == 204
    assert resp.content == b""  # No content
    
    # Verificar que se eliminó de DB
    query = select(MarketSource).where(MarketSource.id == source_id)
    result = await db.execute(query)
    deleted_source = result.scalar_one_or_none()
    assert deleted_source is None


@pytest.mark.asyncio
async def test_delete_source_not_found(client_collab: AsyncClient):
    """Test: 404 cuando fuente no existe"""
    resp = await client_collab.delete("/market/sources/999999")
    
    assert resp.status_code == 404
    data = resp.json()
    assert "no encontrada" in data["detail"].lower()


@pytest.mark.asyncio
async def test_delete_source_updates_product_prices(client_collab: AsyncClient, db: AsyncSession):
    """Test: Eliminar fuente no afecta otras fuentes del mismo producto"""
    from decimal import Decimal
    
    # Crear producto con 2 fuentes
    product = CanonicalProduct(name="Producto Test", ng_sku="NG402")
    db.add(product)
    await db.flush()
    
    source1 = MarketSource(
        product_id=product.id,
        source_name="Fuente 1",
        url="https://example.com/source1",
        last_price=Decimal("100.00"),
        is_mandatory=False
    )
    source2 = MarketSource(
        product_id=product.id,
        source_name="Fuente 2",
        url="https://example.com/source2",
        last_price=Decimal("200.00"),
        is_mandatory=False
    )
    db.add_all([source1, source2])
    await db.commit()
    await db.refresh(source1)
    await db.refresh(source2)
    
    # Eliminar primera fuente
    resp = await client_collab.delete(f"/market/sources/{source1.id}")
    assert resp.status_code == 204
    
    # Verificar que la segunda fuente sigue existiendo
    query = select(MarketSource).where(MarketSource.product_id == product.id)
    result = await db.execute(query)
    remaining_sources = result.scalars().all()
    assert len(remaining_sources) == 1
    assert remaining_sources[0].id == source2.id
