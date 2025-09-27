# NG-HEADER: Nombre de archivo: test_import_access.py
# NG-HEADER: Ubicación: tests/test_import_access.py
# NG-HEADER: Descripción: Pruebas de permisos y acceso a importaciones.
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import pytest

os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test"
os.environ["ADMIN_PASS"] = "test"
os.environ["AUTH_ENABLED"] = "true"

from fastapi.testclient import TestClient

from services.api import app
from db.models import ImportJob, ImportJobRow, Supplier
from services.auth import SessionData, current_session, require_csrf

async def _setup_job() -> int:
    from db.session import SessionLocal
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

client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


@pytest.mark.asyncio
async def test_import_preview_limit() -> None:
    job_id = await _setup_job()
    resp = client.get(f"/imports/{job_id}?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["rows"]) == 2

    app.dependency_overrides[current_session] = lambda: SessionData(None, None, "guest")
    resp = client.get(f"/imports/{job_id}")
    assert resp.status_code == 403
