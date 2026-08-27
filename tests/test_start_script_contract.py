#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_start_script_contract.py
# NG-HEADER: Ubicación: tests/test_start_script_contract.py
# NG-HEADER: Descripción: Contrato estático del launcher raíz y frontend Vue canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_start_uses_vue_as_canonical_frontend() -> None:
    script = (ROOT / "start.bat").read_text(encoding="utf-8")

    assert 'frontend-vue\\package.json' in script
    assert 'pushd "%ROOT%frontend-vue"' in script
    assert "5176" in script
    assert 'if not exist "%ROOT%frontend\\node_modules"' not in script
    assert 'pushd "%ROOT%frontend"' not in script
