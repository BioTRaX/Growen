#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_setup_siyuan_script.py
# NG-HEADER: Ubicación: tests/test_setup_siyuan_script.py
# NG-HEADER: Descripción: Verifica compatibilidad del bootstrap de SiYuan con PowerShell 5.1.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from pathlib import Path


def test_setup_uses_powershell_5_1_compatible_utf8_writer() -> None:
    script = (Path(__file__).parents[1] / "scripts" / "setup-siyuan.ps1").read_text(
        encoding="utf-8"
    )

    assert "utf8NoBOM" not in script
    assert "WriteAllText" in script
    assert "RandomNumberGenerator]::Fill" not in script
    assert "RNGCryptoServiceProvider" in script
    assert "Convert]::ToHexString" not in script
