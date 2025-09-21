#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_purchases_iaval.py
# NG-HEADER: Ubicación: tests/test_purchases_iaval.py
# NG-HEADER: Descripción: Pruebas mínimas para endpoints iAVaL (preview/apply)
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


def _make_supplier(name: str = "Proveedor X") -> int:
    r = client.post("/suppliers", json={"slug": name.lower().replace(" ", "-"), "name": name})
    assert r.status_code in (200, 201)
    return client.get("/suppliers").json()[0]["id"]


def _create_draft_with_pdf(supplier_id: int):
    # Usar el import para crear un borrador con PDF adjunto
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "true"
    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_test.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r = client.post(f"/purchases/import/santaplanta?supplier_id={supplier_id}", files=files)
    assert r.status_code == 200
    assert r.json()["status"] == "BORRADOR"
    return r.json()["purchase_id"]


def test_iaval_preview_and_apply_with_mock(monkeypatch):
    sid = _make_supplier("Proveedor iAVaL")
    pid = _create_draft_with_pdf(sid)

    # Mock de AIRouter.run para devolver una propuesta simple y válida
    def fake_run(task: str, prompt: str):  # noqa: ARG001
        return (
            '{"header": {"remito_number": "R-TEST-OK", "remito_date": "2025-09-02", "vat_rate": 21},'
            ' "lines": [{"index": 0, "fields": {"qty": 2, "unit_cost": 10.5, "line_discount": 0, "supplier_sku": "SKU-1", "title": "Item 1"}}],'
            ' "confidence": 0.9, "comments": ["ok"]}'
        )

    import services.routers.purchases as pr
    monkeypatch.setattr(pr.AIRouter, "run", staticmethod(lambda *_args, **_kwargs: fake_run("", "")))

    # Previo: añadir una línea vacía para que el índice 0 exista
    r = client.put(f"/purchases/{pid}", json={"lines": [{"title": "", "supplier_sku": "", "qty": 1, "unit_cost": 0, "line_discount": 0}]})
    assert r.status_code == 200

    # Preview
    r = client.post(f"/purchases/{pid}/iaval/preview")
    assert r.status_code == 200
    data = r.json()
    assert "proposal" in data and "diff" in data
    assert data["proposal"]["header"]["remito_number"] == "R-TEST-OK"

    # Apply sin log
    r = client.post(f"/purchases/{pid}/iaval/apply", json={"proposal": data["proposal"]})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Verificar que la compra quedó con los valores aplicados
    r = client.get(f"/purchases/{pid}")
    assert r.status_code == 200
    js = r.json()
    assert js["remito_number"] == "R-TEST-OK"
    assert js["vat_rate"] == 21
    assert js["lines"][0]["qty"] == 2
    assert js["lines"][0]["unit_cost"] == 10.5

    # Apply con log
    r = client.post(f"/purchases/{pid}/iaval/apply?emit_log=1", json={"proposal": data["proposal"]})
    assert r.status_code == 200
    js2 = r.json()
    assert js2["ok"] is True
    assert "log" in js2 and js2["log"]["filename"].startswith("iaval_changes_")


def test_iaval_preview_requires_attachment():
    sid = _make_supplier("Proveedor iAVaL 2")
    # Crear compra sin PDF
    r = client.post("/purchases", json={"supplier_id": sid, "remito_number": "R-TEST2", "remito_date": "2025-09-01"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.post(f"/purchases/{pid}/iaval/preview")
    assert r.status_code == 400
    assert "adjunto" in r.json()["detail"].lower()


def test_iaval_preview_with_eml_attachment(monkeypatch):
    sid = _make_supplier("Proveedor iAVaL EML")
    # Crear compra vacía
    r = client.post("/purchases", json={"supplier_id": sid, "remito_number": "R-EML", "remito_date": "2025-09-01"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # Adjuntar un .eml mínimo como si fuera importado
    import base64
    eml_bytes = ("Subject: Pedido 12345 Completado\n\nHTML <b>Remito</b> con 1 item").encode("utf-8")
    files = {"file": ("remito.eml", io.BytesIO(eml_bytes), "message/rfc822")}
    # Reutilizamos endpoint de importación SantaPlanta para adjuntar, si no existe endpoint genérico; como atajo, usamos el de POP
    rr = client.post(f"/purchases/import/pop-email?supplier_id={sid}&kind=eml", files=files)
    assert rr.status_code == 200
    pid2 = rr.json()["purchase_id"]

    # Mock IA para respuesta determinista
    def fake_run(task: str, prompt: str):  # noqa: ARG001
        return (
            '{"header": {"remito_number": "R-EML-OK"}, "lines": [], "confidence": 0.7, "comments": ["desde eml"]}'
        )

    import services.routers.purchases as pr
    monkeypatch.setattr(pr.AIRouter, "run", staticmethod(lambda *_args, **_kwargs: fake_run("", "")))

    r = client.post(f"/purchases/{pid2}/iaval/preview")
    assert r.status_code == 200
    js = r.json()
    assert js["proposal"]["header"]["remito_number"] == "R-EML-OK"
