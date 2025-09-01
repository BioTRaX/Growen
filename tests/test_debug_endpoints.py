# NG-HEADER: Nombre de archivo: test_debug_endpoints.py
# NG-HEADER: Ubicación: tests/test_debug_endpoints.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from fastapi.testclient import TestClient

# Asegurar DB en memoria antes de importar la app
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402

client = TestClient(app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_debug_db() -> None:
    resp = client.get("/debug/db")
    assert resp.status_code == 200
    assert resp.json()["select1"] == 1


def test_debug_config_masks_password(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("DB_URL", "postgresql://user:secret@db/test")
    resp = client.get("/debug/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed_origins"] == ["http://localhost:5173"]
    assert data["db_url"] == "postgresql://user:***@db/test"
    assert "secret" not in data["db_url"]
