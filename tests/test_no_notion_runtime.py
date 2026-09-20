#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_no_notion_runtime.py
# NG-HEADER: Ubicación: tests/test_no_notion_runtime.py
# NG-HEADER: Descripción: Impide reintroducir la integración retirada de Notion.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Notion fue reemplazado por SiYuan y no debe formar parte del runtime."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_notion_runtime_and_dependency_are_absent() -> None:
    forbidden_files = [
        "services/integrations/notion_client.py",
        "services/integrations/notion_errors.py",
        "services/integrations/notion_sections.py",
        "scripts/smoke_notion_sections.py",
    ]
    assert not [path for path in forbidden_files if (ROOT / path).exists()]

    inspected = [
        "services/api.py",
        "services/routers/bug_report.py",
        "services/routers/services_admin.py",
        "cli/ng.py",
        "requirements-base.txt",
        ".env.dev",
        ".env.prod.example",
    ]
    for path in inspected:
        assert "notion" not in (ROOT / path).read_text(encoding="utf-8").lower(), path
