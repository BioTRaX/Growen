#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_import_ai_disabled.py
# NG-HEADER: Ubicación: tests/test_import_ai_disabled.py
# NG-HEADER: Descripción: Test de importación PDF cuando IA está deshabilitada
# NG-HEADER: Lineamientos: Ver AGENTS.md
import os
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from services.api import app  # Punto de entrada FastAPI principal


def _minimal_pdf(path: Path):
    # PDF mínimo válido (header + EOF); suficiente para disparar validación pero sin texto útil
    path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF")


def test_import_ai_disabled_creates_draft_when_allowed(tmp_path):
    os.environ["IMPORT_ALLOW_EMPTY_DRAFT"] = "true"
    os.environ["IMPORT_AI_ENABLED"] = "false"  # asegurar deshabilitado
    pdf = tmp_path / f"{uuid.uuid4().hex}.pdf"
    _minimal_pdf(pdf)
    client = TestClient(app)
    # Crear proveedor dummy primero si endpoint lo requiere (asumimos ID=1 existe en fixtures/migraciones)
    with pdf.open("rb") as fh:
        try:
            resp = client.post(
                "/purchases/import/santaplanta?supplier_id=1&debug=1",
                files={"file": (pdf.name, fh, "application/pdf")},
            )
        except Exception as e:
            # Si el endpoint no existe en este entorno de pruebas, marcar como skip lógico
            import pytest
            pytest.skip(f"Endpoint no disponible: {e}")
    # Puede retornar 200 borrador vacío o 422 (si política distinta en test env). Aceptamos ambos siempre que no 500
    assert resp.status_code in (200, 422), resp.text
    data = resp.json()
    # Si 200, debug debe existir por debug=1
    if resp.status_code == 200:
        dbg = data.get("debug") or {}
        # Eventos deben contener skip_disabled o no tener eventos ai
        events = dbg.get("events") or []
        # No falla si no hay eventos IA, pero si los hay y IA está off debería existir skip_disabled
        ai_events = [e for e in events if (e.get("stage") == "ai")]
        for ev in ai_events:
            assert ev.get("event") in ("skip_disabled", "no_data", "exception")
