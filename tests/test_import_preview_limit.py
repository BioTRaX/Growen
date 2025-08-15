import os
import asyncio

os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient

from services.api import app
from db.base import Base
from db.session import engine


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)


def test_preview_limit() -> None:
    resp = client.post("/suppliers", json={"slug": "santaplanta", "name": "Santa Planta"})
    assert resp.status_code == 200
    supplier_id = resp.json()["id"]

    content = (
        "ID,Producto,Agrupamiento,Familia,SubFamilia,Compra Minima,PrecioDeCompra,PrecioDeVenta\n"
        "1,A,A,F,S,1,10,15\n"
        "2,B,A,F,S,1,20,25\n"
        "3,C,A,F,S,1,30,35\n"
    )
    resp = client.post(
        f"/suppliers/{supplier_id}/price-list/upload",
        data={"dry_run": "true"},
        files={"file": ("test.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    resp = client.get(f"/imports/{job_id}?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 2
