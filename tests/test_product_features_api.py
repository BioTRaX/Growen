# NG-HEADER: Nombre de archivo: test_product_features_api.py
# NG-HEADER: Ubicación: tests/test_product_features_api.py
# NG-HEADER: Descripción: Tests para nuevas funcionalidades de productos como edición de precios y creación de categorías en línea.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.base import Base
from db.session import get_session
from services.api import app
from services.auth import current_session, require_csrf
from tests.test_categories_api import mock_user_session, override_require_csrf

# Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_session():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_session] = override_get_session
app.dependency_overrides[current_session] = mock_user_session
app.dependency_overrides[require_csrf] = override_require_csrf

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    """Fixture to handle database setup and teardown for each test function."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_product_with_new_inline_category(db_session):
    """Test creating a product with a new category inline."""
    response = client.post(
        "/products",
        json={
            "title": "Fertilizante Orgánico",
            "initial_stock": 10,
            "new_category_name": "Fertilizantes",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Fertilizante Orgánico"
    assert data["category_id"] is not None

    # Verify category was created
    cat_response = client.get("/categories")
    assert cat_response.status_code == 200
    cats = cat_response.json()
    assert any(c["name"] == "Fertilizantes" and c["id"] == data["category_id"] for c in cats)

def test_create_product_with_new_inline_subcategory(db_session):
    """Test creating a product with a new sub-category inline."""
    # First, create a parent category
    parent_cat_res = client.post("/categories", json={"name": "Nutrientes"})
    assert parent_cat_res.status_code in (200, 409) # Allow conflict if already exists
    parent_cat_id = parent_cat_res.json()["id"] if parent_cat_res.status_code == 200 else client.get("/categories").json()[0]['id']


    response = client.post(
        "/products",
        json={
            "title": "Booster de Floración",
            "initial_stock": 5,
            "new_category_name": "Boosters",
            "new_category_parent_id": parent_cat_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Booster de Floración"
    assert data["category_id"] is not None

    # Verify category was created with correct parent
    cat_response = client.get(f"/categories")
    assert cat_response.status_code == 200
    cats = cat_response.json()
    new_cat = next((c for c in cats if c["id"] == data["category_id"]), None)
    assert new_cat is not None
    assert new_cat["name"] == "Boosters"
    assert new_cat["parent_id"] == parent_cat_id
    assert new_cat["path"] == "Nutrientes>Boosters"

def test_update_prices(db_session):
    """Test updating purchase and sale prices via the new endpoint."""
    # 1. Create a supplier
    sup_res = client.post("/suppliers", json={"slug": "test-sup", "name": "Test Supplier"})
    assert sup_res.status_code in (200, 409)
    supplier_id = sup_res.json()["id"] if sup_res.status_code == 200 else client.get("/suppliers").json()[0]['id']

    # 2. Create a product and a supplier_product associated with it
    prod_res = client.post("/products", json={
        "title": "Producto de Prueba Precios",
        "supplier_id": supplier_id,
        "supplier_sku": "SKU123"
    })
    assert prod_res.status_code == 200
    product_id = prod_res.json()["id"]
    supplier_product_id = prod_res.json()["supplier_product_id"]
    assert supplier_product_id is not None

    # 3. Update purchase price
    price_update_res = client.patch(
        f"/products/{product_id}/prices",
        json={
            "supplier_item_id": supplier_product_id,
            "purchase_price": 99.99,
        },
    )
    assert price_update_res.status_code == 200
    assert price_update_res.json()["updated_fields"]["purchase_price"] == 99.99

    # 4. Link to a canonical product to test sale_price
    # (Assuming a canonical product needs to be created or exist)
    # This part is complex as it requires a canonical product. Let's simulate it.
    # For a full test, we would need a /canonical-products endpoint to create one.
    # Here, we'll focus on the purchase price part which is self-contained.
    # To test sale_price, we'd need to manually insert CanonicalProduct and ProductEquivalence.
    from db.models import CanonicalProduct, ProductEquivalence
    
    cp = CanonicalProduct(name="Producto Canonico para Precio", sale_price=150.0)
    db_session.add(cp)
    db_session.commit()

    eq = ProductEquivalence(
        supplier_id=supplier_id,
        supplier_product_id=supplier_product_id,
        canonical_product_id=cp.id,
        confidence=1.0,
        source="test"
    )
    db_session.add(eq)
    db_session.commit()

    # 5. Update sale price
    price_update_res_sale = client.patch(
        f"/products/{product_id}/prices",
        json={
            "supplier_item_id": supplier_product_id,
            "sale_price": 199.99,
        },
    )
    assert price_update_res_sale.status_code == 200
    assert price_update_res_sale.json()["updated_fields"]["sale_price"] == 199.99

    # Verify the change in the DB
    updated_cp = db_session.get(CanonicalProduct, cp.id)
    assert updated_cp.sale_price == 199.99
