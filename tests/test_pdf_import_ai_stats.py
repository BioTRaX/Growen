#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_pdf_import_ai_stats.py
# NG-HEADER: Ubicación: tests/test_pdf_import_ai_stats.py
# NG-HEADER: Descripción: Smoke test del endpoint de estadísticas IA de importación PDF
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Prueba básica del endpoint /admin/services/pdf_import/ai_stats.

Valida presencia de claves principales y estructura esperada.
"""
from fastapi.testclient import TestClient

from services.api import app


def test_pdf_import_ai_stats_smoke():
    client = TestClient(app)
    response = client.get("/admin/services/pdf_import/ai_stats")
    if response.status_code == 401:
        return
    assert response.status_code == 200, response.text
    data = response.json()
    expected_keys = [
        "requests",
        "success",
        "success_rate",
        "no_data",
        "skip_disabled",
        "errors",
        "avg_overall_confidence",
        "lines_proposed_total",
        "lines_proposed_avg_per_success",
        "lines_added_total",
        "lines_added_avg_per_success",
        "ignored_low_conf_total",
        "ignored_low_conf_avg_per_success",
        "durations_ms",
        "model_usage",
        "last_24h",
    ]
    for key in expected_keys:
        assert key in data, key
    assert isinstance(data["errors"], dict)
    assert isinstance(data["durations_ms"], dict)
    assert isinstance(data["model_usage"], list)
    assert isinstance(data["last_24h"], dict)
