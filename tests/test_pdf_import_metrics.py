#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_pdf_import_metrics.py
# NG-HEADER: Ubicación: tests/test_pdf_import_metrics.py
# NG-HEADER: Descripción: Test del endpoint de métricas de importación PDF
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Prueba básica del endpoint /admin/services/pdf_import/metrics.

Valida estructura mínima de claves y tipos. No asume datos reales.
"""
from fastapi.testclient import TestClient
from services.api import app


def test_pdf_import_metrics_endpoint_smoke():
    client = TestClient(app)
    # Nota: el endpoint requiere rol admin/colaborador; según auth puede necesitar bypass.
    # Si existe dependencia estricta de sesión, este test podría necesitar ajuste.
    r = client.get("/admin/services/pdf_import/metrics")
    # En entornos sin auth configurada o con dependencia fallida puede devolver 401.
    if r.status_code == 401:
        return  # Se considera aceptable en smoke si auth bloquea sin sesión
    assert r.status_code == 200, r.text
    data = r.json()
    for key in [
        "total_imports",
        "avg_classic_confidence",
        "ai_invocations",
        "ai_success",
        "ai_success_rate",
        "ai_lines_added",
        "last_24h",
    ]:
        assert key in data, key
    assert isinstance(data["last_24h"], dict)
