#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_notion_sections.py
# NG-HEADER: Ubicación: tests/test_notion_sections.py
# NG-HEADER: Descripción: Tests de heurística de secciones y dry-run de Notion (sections)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import os


def test_derive_section_from_url_imports():
    from services.integrations.notion_sections import derive_section_from_url
    assert derive_section_from_url("/compras") == "Compras"
    assert derive_section_from_url("/purchases") == "Compras"
    assert derive_section_from_url("/stock") == "Stock"
    assert derive_section_from_url("/admin") == "Admin"
    assert derive_section_from_url("/") == "App"
    assert derive_section_from_url(None) == "App"
    assert derive_section_from_url("") == "App"
    assert derive_section_from_url("/proveedores") == "Proveedores"


def test_upsert_dry_run_returns_simulated_title(monkeypatch):
    # Forzar modo sections y dry-run
    monkeypatch.setenv("NOTION_FEATURE_ENABLED", "1")
    monkeypatch.setenv("NOTION_MODE", "sections")
    monkeypatch.setenv("NOTION_DRY_RUN", "1")
    monkeypatch.setenv("NOTION_ERRORS_DATABASE_ID", "fake-db-id")

    from services.integrations.notion_sections import upsert_report_as_child

    r = upsert_report_as_child("http://localhost:5173/compras/lista", "msg", None, "br-123")
    assert r.get("action") == "dry-run"
    assert r.get("parent") == "Compras"
    assert isinstance(r.get("title"), str) and r["title"].endswith("br-123")
