import os
import asyncio

# Configurar DB en memoria antes de importar la app
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from services.api import app
from db.base import Base
from db.session import engine, SessionLocal
from db.models import Supplier, SupplierFile


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)


def test_supplier_crud() -> None:
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp", "name": "Santa Planta"})
    assert resp.status_code == 200
    data = resp.json()
    supplier_id = data["id"]

    # Listar proveedores
    resp = client.get("/suppliers")
    assert resp.status_code == 200
    assert any(s["slug"] == "sp" for s in resp.json())

    # Insertar archivo asociado para probar listado de files
    async def _add_file() -> None:
        async with SessionLocal() as session:  # type: AsyncSession
            file = SupplierFile(
                supplier_id=supplier_id,
                filename="test.csv",
                sha256="abc",
                rows=1,
            )
            session.add(file)
            await session.commit()
    asyncio.get_event_loop().run_until_complete(_add_file())

    # Listar archivos del proveedor
    resp = client.get(f"/suppliers/{supplier_id}/files")
    assert resp.status_code == 200
    files = resp.json()
    assert files and files[0]["filename"] == "test.csv"

    # Actualizar nombre del proveedor
    resp = client.patch(
        f"/suppliers/{supplier_id}", json={"name": "Proveedor X"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Proveedor X"


def test_supplier_slug_conflict() -> None:
    resp = client.post("/suppliers", json={"slug": "dup", "name": "A"})
    assert resp.status_code == 200
    resp = client.post("/suppliers", json={"slug": "dup", "name": "B"})
    assert resp.status_code == 409
    assert resp.json()["message"] == "Slug ya utilizado"


def test_supplier_missing_fields() -> None:
    resp = client.post("/suppliers", json={"slug": "xx"})
    assert resp.status_code == 400
    assert resp.json()["message"] == "Faltan campos"

    resp = client.post(
        "/suppliers", data="no-json", headers={"Content-Type": "text/plain"}
    )
    assert resp.status_code == 415
