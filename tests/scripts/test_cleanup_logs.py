import os
import io
import time
from pathlib import Path
import subprocess

import pytest

LOGS = Path("logs")
SCRIPT = Path("scripts/cleanup_logs.py")

pytestmark = pytest.mark.asyncio


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def run(cmd: list[str]):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def test_cleanup_logs_dry_run(tmp_path, monkeypatch):
    # Preparar entorno aislado: cambiar CWD temporalmente
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "scripts").mkdir()
        (tmp_path / "logs").mkdir()
        # Copiar script
        script_dst = tmp_path / SCRIPT
        script_src = Path.cwd().parent / SCRIPT if (Path.cwd().parent / SCRIPT).exists() else Path(__file__).resolve().parents[2] / SCRIPT
        script_dst.write_text(script_src.read_text(encoding="utf-8"), encoding="utf-8")
        # Crear archivos
        write(tmp_path / "logs" / "backend.log", "OLD")
        write(tmp_path / "logs" / "backend.log.20240101.bak", "BAK")
        out = run(["python", str(script_dst), "--dry-run"]).stdout
        assert "backend.log" in out
        # En dry-run no debe borrarse backup
        assert (tmp_path / "logs" / "backend.log.20240101.bak").exists()
    finally:
        os.chdir(cwd)


def test_cleanup_logs_real(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "scripts").mkdir()
        (tmp_path / "logs").mkdir()
        script_dst = tmp_path / SCRIPT
        script_src = Path.cwd().parent / SCRIPT if (Path.cwd().parent / SCRIPT).exists() else Path(__file__).resolve().parents[2] / SCRIPT
        script_dst.write_text(script_src.read_text(encoding="utf-8"), encoding="utf-8")
        write(tmp_path / "logs" / "backend.log", "MUCHO TEXTO")
        write(tmp_path / "logs" / "backend.log.20240101.bak", "BAK")
        run(["python", str(script_dst)])
        # backup debe desaparecer
        assert not (tmp_path / "logs" / "backend.log.20240101.bak").exists()
        # backend.log truncado
        assert (tmp_path / "logs" / "backend.log").read_text(encoding="utf-8") == ""
    finally:
        os.chdir(cwd)
