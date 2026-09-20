#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_canonical_products_api.py
# NG-HEADER: Ubicación: tests/test_canonical_products_api.py
# NG-HEADER: Descripción: Pruebas para POST /canonical-products (autogeneración SKU)
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


def test_create_canonical_requires_category_and_subcategory() -> None:
    r = client.post("/canonical-products", json={"name": "Maceta plástica 1L"})
    assert r.status_code == 422


def test_create_canonical_with_category_sequences_increase() -> None:
    # Crear categoría raíz
    r = client.post("/categories", json={"name": "Riego", "kind": "category"})
    if r.status_code == 200:
        cat = r.json()
    else:
        # categoría puede existir por ejecuciones previas
        assert r.status_code in (409, 200)
        lr = client.get("/categories")
        assert lr.status_code == 200
        cats = lr.json()
        cat = next(c for c in cats if c.get("name") == "Riego" and c.get("kind") == "category")
    sub_response = client.post("/categories", json={"name": "Bombas", "kind": "subcategory"})
    if sub_response.status_code == 200:
        sub = sub_response.json()
    else:
        sub = next(c for c in client.get("/categories").json() if c.get("name") == "Bombas" and c.get("kind") == "subcategory")

    # Crear 2 canónicos en misma categoría -> secuencias 0001 y 0002
    r1 = client.post("/canonical-products", json={"name": "Bomba 12v", "category_id": cat["id"], "subcategory_id": sub["id"]})
    r2 = client.post("/canonical-products", json={"name": "Manguera 1/2", "category_id": cat["id"], "subcategory_id": sub["id"]})
    assert r1.status_code == 200 and r2.status_code == 200
    s1 = r1.json()["sku_custom"]
    s2 = r2.json()["sku_custom"]
    n1 = int(s1.split("_")[1])
    n2 = int(s2.split("_")[1])
    assert n2 == n1 + 1
    assert len(s1.split("_")[1]) == len(s2.split("_")[1]) == 4
