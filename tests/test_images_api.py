# NG-HEADER: Nombre de archivo: test_images_api.py
# NG-HEADER: Ubicación: tests/test_images_api.py
# NG-HEADER: Descripción: Pruebas de la API de imágenes.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import io
import pytest

os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test"
os.environ["ADMIN_PASS"] = "test"
os.environ["AUTH_ENABLED"] = "true"
os.environ["MEDIA_ROOT"] = "./ImagenesTest"
os.environ["CLAMAV_ENABLED"] = "false"
os.environ["IMAGE_MIN_SIZE"] = "1"

from fastapi.testclient import TestClient

from services.api import app
from services.auth import SessionData, current_session, require_csrf
from db.models import Product

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def _png_bytes() -> bytes:
    # 1x1 transparent PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.mark.asyncio
async def test_upload_from_multipart() -> None:
    from db.session import SessionLocal
    # Create product
    async with SessionLocal() as db:
        p = Product(sku_root="X", title="Test")
        db.add(p)
        await db.commit()
        await db.refresh(p)
        pid = p.id

    files = {"file": ("tiny.png", _png_bytes(), "image/png")}
    r = client.post(f"/products/{pid}/images/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["image_id"] > 0
