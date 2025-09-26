# NG-HEADER: Nombre de archivo: test_images_api.py
# NG-HEADER: Ubicación: tests/test_images_api.py
# NG-HEADER: Descripción: Pruebas de la API de imágenes.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import io
import asyncio

os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test"
os.environ["ADMIN_PASS"] = "test"
os.environ["AUTH_ENABLED"] = "true"
os.environ["MEDIA_ROOT"] = "./ImagenesTest"
os.environ["CLAMAV_ENABLED"] = "false"
os.environ["IMAGE_MIN_SIZE"] = "1"

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from services.api import app
from services.auth import SessionData, current_session, require_csrf
from db.base import Base
from db.session import engine, SessionLocal
from db.models import Product


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _png_bytes() -> bytes:
    # 1x1 transparent PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_upload_from_multipart() -> None:
    # Create product
    async def _create() -> int:
        async with SessionLocal() as db:
            p = Product(sku_root="X", title="Test")
            db.add(p)
            await db.commit()
            await db.refresh(p)
            return p.id
    pid = asyncio.get_event_loop().run_until_complete(_create())

    files = {"file": ("tiny.png", _png_bytes(), "image/png")}
    r = client.post(f"/products/{pid}/images/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["image_id"] > 0

