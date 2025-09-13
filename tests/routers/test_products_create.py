import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.api import app
from db.session import get_session
from db.models import Product

pytestmark = pytest.mark.asyncio

# Nota: se asume entorno dev => rol admin implícito si no hay cookie.

async def test_create_product_basic(monkeypatch):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Primero crear producto simple
        r = await ac.post("/products", json={"title": "Widget Test", "initial_stock": 5})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["title"] == "Widget Test"
        assert data["stock"] == 5
        assert data["sku_root"][:6].isupper()
        assert data["slug"].startswith("widget-test")

async def test_create_product_with_category_invalid():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/products", json={"title": "Otro", "category_id": 999999})
        assert r.status_code == 400
        assert "category_id" in r.text.lower()

async def test_create_product_negative_stock():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/products", json={"title": "Bad", "initial_stock": -1})
        assert r.status_code == 400
        assert "initial_stock" in r.text.lower()
