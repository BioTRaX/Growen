import os
import asyncio
from io import BytesIO

import pandas as pd

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
    resp = client.post("/suppliers", json={"slug": "santa-planta", "name": "Santa Planta"})
    assert resp.status_code == 200
    supplier_id = resp.json()["id"]

    df = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Producto": ["A", "B", "C"],
            "PrecioDeCompra": [10, 20, 30],
            "PrecioDeVenta": [15, 25, 35],
        }
    )
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    resp = client.post(
        f"/suppliers/{supplier_id}/price-list/upload",
        data={"dry_run": "true"},
        files={
            "file": (
                "test.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    resp = client.get(f"/imports/{job_id}?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 2
