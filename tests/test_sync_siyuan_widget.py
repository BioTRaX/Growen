#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: test_sync_siyuan_widget.py
# NG-HEADER: Ubicación: tests/test_sync_siyuan_widget.py
# NG-HEADER: Descripción: Prueba el diagnóstico y la sincronización segura de widgets SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync-siyuan-widget.ps1"


def _run_sync(repo: Path, workspace: Path, *, apply: bool = False) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        "-WidgetName",
        "demo",
        "-RepositoryRoot",
        str(repo),
        "-WorkspaceRoot",
        str(workspace),
    ]
    if apply:
        command.append("-Apply")
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_detects_drift_and_only_syncs_runtime_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "siyuan-widgets" / "demo"
    workspace = tmp_path / "workspace"
    target = workspace / "data" / "widgets" / "demo"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    (source / "index.html").write_text("<main>nuevo</main>", encoding="utf-8")
    (source / "script.js").write_text("const version = 2;", encoding="utf-8")
    (source / "README.md").write_text("no desplegar", encoding="utf-8")
    (target / "index.html").write_text("<main>viejo</main>", encoding="utf-8")

    drift = _run_sync(repo, workspace)
    assert drift.returncode == 1
    assert "DESINCRONIZADO" in drift.stdout, drift.stderr
    assert (target / "index.html").read_text(encoding="utf-8") == "<main>viejo</main>"

    applied = _run_sync(repo, workspace, apply=True)
    assert applied.returncode == 0, applied.stderr
    assert (target / "index.html").read_text(encoding="utf-8") == "<main>nuevo</main>"
    assert (target / "script.js").read_text(encoding="utf-8") == "const version = 2;"
    assert not (target / "README.md").exists()

    verified = _run_sync(repo, workspace)
    assert verified.returncode == 0, verified.stderr
    assert "SINCRONIZADO" in verified.stdout


def test_resolves_default_roots_from_the_script_location(tmp_path: Path) -> None:
    repo = tmp_path / "Growen"
    script = repo / "scripts" / SCRIPT.name
    source = repo / "siyuan-widgets" / "demo"
    target = tmp_path / "growen-siyuan" / "workspace" / "data" / "widgets" / "demo"
    script.parent.mkdir(parents=True)
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    shutil.copy2(SCRIPT, script)
    (source / "index.html").write_text("<main>igual</main>", encoding="utf-8")
    (target / "index.html").write_text("<main>igual</main>", encoding="utf-8")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-WidgetName",
            "demo",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SINCRONIZADO" in result.stdout
