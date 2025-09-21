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
    assert r.json().get("already_confirmed") in (None, False)

    # Idempotencia (mismo remito)
    r = client.post("/purchases", json=payload)
    assert r.status_code == 409


def test_confirm_idempotent_and_autolink_flow():
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_auto", "name": "Proveedor Auto"})
    assert resp.status_code in (200, 201)
    supplier_id = client.get("/suppliers").json()[0]["id"]

    # Crear producto mínimo con SKU interno distinto al del proveedor y link mediante endpoint dedicado
    # 1) Crear producto mínimo
    prod = client.post(
        "/catalog/products",
        json={
            "title": "Maceta 12cm",
            "initial_stock": 0,
            "supplier_id": supplier_id,
            "supplier_sku": "SP-001",
            "sku": "NG-MAC12",
        },
    )
    assert prod.status_code == 200
    # El endpoint de creación mínima ya crea SupplierProduct con internal_product_id/internal_variant_id
    # y devuelve supplier_item_id; no es necesario llamar a /supplier-products/link aquí.
    supplier_item_id = prod.json()["supplier_item_id"]

    # Crear compra con una línea que tenga sólo supplier_sku (autolink debe completarla)
    payload = {"supplier_id": supplier_id, "remito_number": "R-AL-1", "remito_date": "2025-08-31"}
    r = client.post("/purchases", json=payload)
    assert r.status_code == 200
    pid = r.json()["id"]

    # Agregar línea a la compra
    r = client.put(
        f"/purchases/{pid}",
        json={
            "lines": [
                {
                    "supplier_sku": "SP-001",
                    "title": "Maceta 12cm",
                    "qty": 3,
                    "unit_cost": 100.0,
                    "line_discount": 0.0,
                }
            ]
        },
    )
    assert r.status_code == 200

    # Confirmar: debe autovincular la línea al supplier_item y sumar stock 3 al producto
    r1 = client.post(f"/purchases/{pid}/confirm")
    assert r1.status_code == 200
    assert r1.json().get("already_confirmed") in (None, False)

    # Confirmación repetida: idempotente, no debe volver a sumar stock ni duplicar price history
    r2 = client.post(f"/purchases/{pid}/confirm")
    assert r2.status_code == 200
    assert r2.json().get("already_confirmed") is True


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


def test_import_santaplanta_pdf_policy(tmp_path):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_policy", "name": "Santa Planta Policy"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # PDF mínimo (garantizado sin líneas extraíbles)
    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_policy.pdf", io.BytesIO(dummy_pdf), "application/pdf")}

    # --- Política: IMPORT_ALLOW_EMPTY_DRAFT = true (default) ---
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "true"
    r_allow = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files)
    assert r_allow.status_code == 200
    assert r_allow.json()["status"] == "BORRADOR"
    assert "purchase_id" in r_allow.json()

    # --- Política: IMPORT_ALLOW_EMPTY_DRAFT = false ---
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "false"
    # Re-abrir el BytesIO para la nueva request
    files_false = {"file": ("remito_policy_false.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r_disallow = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files_false)
    assert r_disallow.status_code == 422
    assert "No se detectaron líneas" in r_disallow.json()["detail"]["detail"]

    # Limpiar variable de entorno
    del os.environ["IMPORT_ALLOW_EMPTY_DRAFT"]


def test_import_santaplanta_pdf_force_ocr(tmp_path, monkeypatch):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_ocr", "name": "Santa Planta OCR"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # Mock de run_ocrmypdf para no depender del binario
    def mock_ocr(*args, **kwargs):
        # Simula que OCR se ejecutó y creó un archivo de salida
        # El contenido no importa, solo que exista
        output_path = args[1]
        with open(output_path, "wb") as f:
            f.write(b"%PDF-1.4\n%OCR'd\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF")
        return True, "stdout mock", "stderr mock"

    monkeypatch.setattr("services.importers.santaplanta_pipeline.run_ocrmypdf", mock_ocr)

    dummy_pdf = b"%PDF-1.4\n%no text\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_ocr.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    
    # Llamada con force_ocr=1
    r = client.post(f"/purchases/import/santaplanta?supplier_id={idx}&force_ocr=1", files=files)
    
    # Como el mock de OCR no produce líneas, el resultado depende de la política de empty draft
    if os.getenv("IMPORT_ALLOW_EMPTY_DRAFT", "true").lower() == "true":
        assert r.status_code == 200
        assert r.json()["status"] == "BORRADOR"
    else:
        assert r.status_code == 422
