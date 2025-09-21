#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_pytest_filter_arc4.py
# NG-HEADER: Ubicación: tests/test_pytest_filter_arc4.py
# NG-HEADER: Descripción: Verifica que Pytest trate CryptographyDeprecationWarning ARC4 como error
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Asegura que los tests fallen ante advertencias ARC4 según la política de seguridad."""
import pytest


def test_arc4_warning_marked_as_error(pytestconfig: pytest.Config) -> None:
    filters = pytestconfig.getini("filterwarnings")
    assert any(
        "cryptography.utils.CryptographyDeprecationWarning" in fw and fw.strip().startswith("error")
        for fw in filters
    ), "Falta filtro 'error' para CryptographyDeprecationWarning (ARC4) en pytest.ini"
