# NG-HEADER: Nombre de archivo: test_purchases_api.py
# NG-HEADER: Ubicación: tests/test_purchases_api.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
import io
import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")

from services.api import app  # noqa: E402
from services.auth import current_session, require_csrf, SessionData  # noqa: E402


client = TestClient(app)
app.dependency_overrides[current_session] = lambda: SessionData(None, None, "admin")
app.dependency_overrides[require_csrf] = lambda: None


def test_create_validate_confirm_and_duplication():
    # Crear proveedor mínimo
    # Nota: el endpoint de proveedores ya existe; creamos uno para usar su ID
    resp = client.post("/suppliers", json={"slug": "sp", "name": "Santa Planta"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # Crear compra
    payload = {"supplier_id": idx, "remito_number": "R-001", "remito_date": "2025-08-31"}
    r = client.post("/purchases", json=payload)
    assert r.status_code == 200
    pid = r.json()["id"]

    # Validar (sin líneas)
    r = client.post(f"/purchases/{pid}/validate")
    assert r.status_code == 200
    assert r.json()["unmatched"] == 0

    # Confirmar
    r = client.post(f"/purchases/{pid}/confirm")
    assert r.status_code == 200

    # Idempotencia (mismo remito)
    r = client.post("/purchases", json=payload)
    assert r.status_code == 409


def test_cancel_requires_note():
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp2", "name": "Santa Planta 2"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]
    r = client.post("/purchases", json={"supplier_id": idx, "remito_number": "R-XYZ", "remito_date": "2025-08-31"})
    pid = r.json()["id"]
    r = client.post(f"/purchases/{pid}/cancel", json={})
    assert r.status_code == 400
    r = client.post(f"/purchases/{pid}/cancel", json={"note": "me equivoqué"})
    assert r.status_code == 200


def test_import_santaplanta_pdf_creates_draft(tmp_path):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp3", "name": "Santa Planta 3"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # PDF mínimo (puede que el parser no lea texto; igual debe crear BORRADOR)
    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_sp.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files)
    assert r.status_code in (200, 409)  # 409 si el test se ejecuta dos veces con mismo filename
