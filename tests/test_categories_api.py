#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_categories_api.py
# NG-HEADER: Ubicación: tests/test_categories_api.py
# NG-HEADER: Descripción: Pruebas para POST /categories (unicidad y validación de parent)
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402


client = TestClient(app)

# Forzar rol admin y desactivar CSRF en tests
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def test_create_category_basic_and_uniqueness() -> None:
    # Crear raíz "Grow" (idempotente: si existe, reutilizarla)
    r = client.post("/categories", json={"name": "Grow"})
    if r.status_code == 200:
        root = r.json()
    else:
        # Ya existe: buscarla en la lista
        assert r.status_code == 409
        lr = client.get("/categories")
        assert lr.status_code == 200
        data = lr.json()
        root = next((c for c in data if c.get("name") == "Grow" and c.get("parent_id") is None), None)
        assert root, "Root category 'Grow' should exist for this test"
    assert root["name"] == "Grow"
    assert root["parent_id"] is None

    # Crear hijo único "Sustratos" bajo raíz
    r = client.post("/categories", json={"name": "Sustratos", "parent_id": root["id"]})
    if r.status_code == 200:
        child = r.json()
    else:
        # Si ya existe por ejecuciones previas, validar conflicto y tomar existente
        assert r.status_code == 409
        lr = client.get("/categories")
        assert lr.status_code == 200
        data = lr.json()
        child = next((c for c in data if c.get("name") == "Sustratos" and c.get("parent_id") == root["id"]), None)
        assert child, "Child category should exist under root"
    assert child["parent_id"] == root["id"]
    assert child["path"].endswith(">Sustratos") or child["path"] == "Grow>Sustratos"

    # Intentar duplicar en mismo nivel -> 409
    r = client.post("/categories", json={"name": "Sustratos", "parent_id": root["id"]})
    assert r.status_code == 409
    assert "existe" in r.json().get("detail", "").lower()

    # Mismo nombre en otro nivel debe permitirse. Si ya existe previamente en raíz, aceptamos 409 como idempotencia del entorno
    r = client.post("/categories", json={"name": "Sustratos"})
    if r.status_code == 200:
        data = r.json()
        assert data["name"] == "Sustratos" and data["parent_id"] is None
    else:
        assert r.status_code == 409
        lr = client.get("/categories")
        assert lr.status_code == 200
        cats = lr.json()
        assert any(c.get("name") == "Sustratos" and c.get("parent_id") is None for c in cats)


def test_create_category_invalid_parent() -> None:
    r = client.post("/categories", json={"name": "Iluminacion", "parent_id": 999999})
    assert r.status_code == 400
    assert "parent_id" in r.json().get("detail", "")
