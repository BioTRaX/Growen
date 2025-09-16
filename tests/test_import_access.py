# NG-HEADER: Nombre de archivo: test_import_access.py
# NG-HEADER: Ubicación: tests/test_import_access.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import asyncio

os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test"
os.environ["ADMIN_PASS"] = "test"
os.environ["AUTH_ENABLED"] = "true"

from fastapi.testclient import TestClient

from services.api import app
from db.base import Base
from db.session import engine, SessionLocal
from db.models import ImportJob, ImportJobRow, Supplier
from services.auth import SessionData, current_session, require_csrf

async def _init_db() -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    import uuid
    async with SessionLocal() as session:
        # Usar slug único por corrida para evitar UNIQUE constraint failed en re-ejecuciones / importaciones repetidas
        supplier = Supplier(slug=f"s1-{uuid.uuid4().hex[:8]}", name="S1")
        session.add(supplier)
        await session.flush()
        job = ImportJob(supplier_id=supplier.id, filename="x.xlsx", status="DRY_RUN")
        session.add(job)
        await session.flush()
        for i in range(3):
            session.add(
                ImportJobRow(
                    job_id=job.id,
                    row_index=i,
                    status="ok",
                    error=None,
                    row_json_normalized={},
                )
            )
        await session.commit()
        return job.id

job_id = asyncio.get_event_loop().run_until_complete(_init_db())

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def test_import_preview_limit() -> None:
    resp = client.get(f"/imports/{job_id}?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["rows"]) == 2

    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "guest")
    resp = client.get(f"/imports/{job_id}")
    assert resp.status_code == 403
