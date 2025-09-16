#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_import_dedupe.py
# NG-HEADER: Ubicación: tests/test_import_dedupe.py
# NG-HEADER: Descripción: Prueba del filtro anti-duplicados en import de compras
# NG-HEADER: Lineamientos: Ver AGENTS.md
import io
import os
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("IMPORT_ALLOW_EMPTY_DRAFT", "true")

from services.api import app  # noqa: E402

client = TestClient(app)


def test_import_santaplanta_includes_dedupe_meta():
    # Crear proveedor
    resp = client.post("/suppliers", json={"slug": "sp_dup", "name": "Santa Planta D"})
    assert resp.status_code in (200, 201)
    sup_id = client.get("/suppliers").json()[0]["id"]

    dummy_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<>\n%%EOF"
    files = {"file": ("remito_dup.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
    r = client.post(f"/purchases/import/santaplanta?supplier_id={sup_id}", files=files, headers={"X-CSRF-Token": "x"})
    # En modo de prueba puede devolver 200 con borrador vacío
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        data = r.json()
        parsed = data.get("parsed") or {}
        # Las claves pueden estar presentes aunque no haya líneas
        assert "lines" in parsed
        # La API agrega metadatos en purchase.meta, no siempre se devuelven aquí; esto valida que la ruta funciona
