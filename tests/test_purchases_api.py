# NG-HEADER: Nombre de archivo: test_purchases_api.py
# NG-HEADER: UbicaciÃ³n: tests/test_purchases_api.py
# NG-HEADER: DescripciÃ³n: Pendiente de descripciÃ³n
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
    # Crear proveedor mÃ­nimo
    # Nota: el endpoint de proveedores ya existe; creamos uno para usar su ID
    resp = client.post("/suppliers", json={"slug": "sp", "name": "Santa Planta"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # Crear compra
    payload = {"supplier_id": idx, "remito_number": "R-001", "remito_date": "2025-08-31"}
    r = client.post("/purchases", json=payload)
    assert r.status_code == 200
    pid = r.json()["id"]

    # Validar (sin lÃ­neas)
    r = client.post(f"/purchases/{pid}/validate")
    assert r.status_code == 200
    assert r.json()["unmatched"] == 0

    # Confirmar
    r = client.post(f"/purchases/{pid}/confirm?debug=1")
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

    # Crear producto mÃ­nimo con SKU interno distinto al del proveedor y link mediante endpoint dedicado
    # 1) Crear producto mÃ­nimo
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
    # El endpoint de creaciÃ³n mÃ­nima ya crea SupplierProduct con internal_product_id/internal_variant_id
    # y devuelve supplier_item_id; no es necesario llamar a /supplier-products/link aquÃ­.
    supplier_item_id = prod.json()["supplier_item_id"]

    # Crear compra con una lÃ­nea que tenga sÃ³lo supplier_sku (autolink debe completarla)
    payload = {"supplier_id": supplier_id, "remito_number": "R-AL-1", "remito_date": "2025-08-31"}
    r = client.post("/purchases", json=payload)
    assert r.status_code == 200
    pid = r.json()["id"]

    # Agregar lÃ­nea a la compra
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

    # Confirmar: debe autovincular la lÃ­nea al supplier_item y sumar stock 3 al producto
    r1 = client.post(f"/purchases/{pid}/confirm")
    assert r1.status_code == 200
    body = r1.json()
    assert body.get("already_confirmed") in (None, False)
    deltas = body.get("applied_deltas") or []
    assert any(d.get("line_title") == "Maceta 12cm" for d in deltas)

    # ConfirmaciÃ³n repetida: idempotente, no debe volver a sumar stock ni duplicar price history
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
    r = client.post(f"/purchases/{pid}/cancel", json={"note": "me equivoquÃ©"})
    assert r.status_code == 200


def test_import_santaplanta_pdf_creates_draft(tmp_path):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp3", "name": "Santa Planta 3"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # PDF mÃ­nimo (puede que el parser no lea texto; igual debe crear BORRADOR)
    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_sp.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files)
    assert r.status_code in (200, 409)  # 409 si el test se ejecuta dos veces con mismo filename


def test_import_santaplanta_pdf_policy(tmp_path):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_policy", "name": "Santa Planta Policy"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # PDF mÃ­nimo (garantizado sin lÃ­neas extraÃ­bles)
    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_policy.pdf", io.BytesIO(dummy_pdf), "application/pdf")}

    # --- PolÃ­tica: IMPORT_ALLOW_EMPTY_DRAFT = true (default) ---
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "true"
    r_allow = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files)
    assert r_allow.status_code == 200
    assert r_allow.json()["status"] == "BORRADOR"
    assert "purchase_id" in r_allow.json()

    # --- PolÃ­tica: IMPORT_ALLOW_EMPTY_DRAFT = false ---
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "false"
    # Re-abrir el BytesIO para la nueva request
    files_false = {"file": ("remito_policy_false.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r_disallow = client.post(f"/purchases/import/santaplanta?supplier_id={idx}", files=files_false)
    assert r_disallow.status_code == 422
    assert "No se detectaron lÃ­neas" in r_disallow.json()["detail"]["detail"]

    # Limpiar variable de entorno
    del os.environ["IMPORT_ALLOW_EMPTY_DRAFT"]


def test_import_santaplanta_pdf_force_ocr(tmp_path, monkeypatch):
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_ocr", "name": "Santa Planta OCR"})
    assert resp.status_code in (200, 201)
    idx = client.get("/suppliers").json()[0]["id"]

    # Mock de run_ocrmypdf para no depender del binario
    def mock_ocr(*args, **kwargs):
        # Simula que OCR se ejecutÃ³ y creÃ³ un archivo de salida
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
    
    # Como el mock de OCR no produce lÃ­neas, el resultado depende de la polÃ­tica de empty draft
    if os.getenv("IMPORT_ALLOW_EMPTY_DRAFT", "true").lower() == "true":
        assert r.status_code == 200
        assert r.json()["status"] == "BORRADOR"
    else:
        assert r.status_code == 422

def test_update_purchase_cleans_links_when_sku_changes():
    resp = client.post("/suppliers", json={"slug": "sp_clean", "name": "Proveedor Clean"})
    assert resp.status_code in (200, 201)
    supplier_id = resp.json()["id"]

    first_product = client.post(
        "/catalog/products",
        json={
            "title": "Producto Clean 1",
            "initial_stock": 0,
            "supplier_id": supplier_id,
            "supplier_sku": "CLEAN-001",
            "sku": "NG-CLEAN-1",
        },
    )
    assert first_product.status_code == 200
    supplier_item_one = first_product.json()["supplier_item_id"]

    second_product = client.post(
        "/catalog/products",
        json={
            "title": "Producto Clean 2",
            "initial_stock": 0,
            "supplier_id": supplier_id,
            "supplier_sku": "CLEAN-002",
            "sku": "NG-CLEAN-2",
        },
    )
    assert second_product.status_code == 200
    supplier_item_two = second_product.json()["supplier_item_id"]

    purchase = client.post(
        "/purchases",
        json={"supplier_id": supplier_id, "remito_number": "R-CLEAN", "remito_date": "2025-09-20"},
    )
    assert purchase.status_code == 200
    pid = purchase.json()["id"]

    create_line = client.put(
        f"/purchases/{pid}",
        json={
            "lines": [
                {
                    "supplier_item_id": supplier_item_one,
                    "supplier_sku": "CLEAN-001",
                    "title": "Producto Clean 1",
                    "qty": 5,
                    "unit_cost": 100.0,
                    "line_discount": 0.0,
                }
            ]
        },
    )
    assert create_line.status_code == 200

    purchase_data = client.get(f"/purchases/{pid}").json()
    assert purchase_data["lines"], "se esperaba al menos una linea"
    line = purchase_data["lines"][0]
    line_id = line["id"]
    assert line.get("supplier_item_id") == supplier_item_one
    assert line.get("product_id") is not None

    update_line = client.put(
        f"/purchases/{pid}",
        json={
            "lines": [
                {
                    "id": line_id,
                    "supplier_sku": "CLEAN-NEW",
                    "title": "Producto editado",
                    "qty": 5,
                    "unit_cost": 110.0,
                }
            ]
        },
    )
    assert update_line.status_code == 200

    purchase_after_sku = client.get(f"/purchases/{pid}").json()["lines"][0]
    assert purchase_after_sku.get("supplier_item_id") is None
    assert purchase_after_sku.get("product_id") is None
    assert purchase_after_sku.get("state") == "SIN_VINCULAR"

    relink = client.put(
        f"/purchases/{pid}",
        json={
            "lines": [
                {
                    "id": line_id,
                    "supplier_item_id": supplier_item_two,
                    "supplier_sku": "CLEAN-002",
                    "title": "Producto final",
                    "qty": 5,
                    "unit_cost": 120.0,
                }
            ]
        },
    )
    assert relink.status_code == 200

    purchase_final = client.get(f"/purchases/{pid}").json()["lines"][0]
    assert purchase_final.get("supplier_item_id") == supplier_item_two
    assert purchase_final.get("product_id") is not None
    assert purchase_final.get("state") == "OK"
    assert purchase_final.get("supplier_sku") == "CLEAN-002"


