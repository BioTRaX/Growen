#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_audit_docs.py
# NG-HEADER: Ubicación: tests/test_audit_docs.py
# NG-HEADER: Descripción: Pruebas del auditor documental.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path

from scripts.audit_docs import audit


def test_audit_detects_missing_header_and_stale_reference(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "bad.md").write_text("FEATURES_PENDIENTES.md", encoding="utf-8")
    findings = audit(tmp_path)
    assert any(item.startswith("header_missing:") for item in findings)
    assert any(item.startswith("stale_reference:") for item in findings)
