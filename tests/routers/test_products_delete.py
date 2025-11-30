import pytest
from httpx import AsyncClient, ASGITransport

from services.api import app

pytestmark = pytest.mark.asyncio

async def test_delete_products_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Crear dos productos
        r1 = await ac.post("/products", json={"title": "A Borrar 1"})
        r2 = await ac.post("/products", json={"title": "A Borrar 2"})
        assert r1.status_code == 200 and r2.status_code == 200
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]
        # Borrar
        delr = await ac.request("DELETE", "/products", json={"ids": [id1, id2]})
        assert delr.status_code == 200, delr.text
        data = delr.json()
        assert data["deleted"] == 2
        # Verificar que ya no existen
        g1 = await ac.get(f"/products/{id1}")
        g2 = await ac.get(f"/products/{id2}")
        assert g1.status_code == 404
        assert g2.status_code == 404
