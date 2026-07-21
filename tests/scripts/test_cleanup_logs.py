# NG-HEADER: Nombre de archivo: test_cleanup_logs.py
# NG-HEADER: Ubicación: tests/scripts/test_cleanup_logs.py
# NG-HEADER: Descripción: Pruebas de la limpieza canónica de logs físicos y carpetas de desarrollo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from services.logging.log_cleanup import build_cleanup_plan, execute_cleanup_plan


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "cleanup_logs.py"
pytestmark = pytest.mark.no_db


def write(path: Path, content: str = "LOG") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_script(log_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--log-root", str(log_root), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )


def test_dry_run_does_not_modify_logs_or_directories(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    write(log_root / "backend.log", "BACKEND")
    write(log_root / "dev" / "20260701_100000" / "api.stderr.log")
    write(log_root / "dev" / "20260702_100000" / "state.json", "{}")

    result = run_script(log_root, "--dry-run", "--keep-days", "0")

    assert "20260701_100000" in result.stdout
    assert (log_root / "backend.log").read_text(encoding="utf-8") == "BACKEND"
    assert (log_root / "dev" / "20260701_100000").is_dir()


def test_cleanup_removes_old_run_directory_and_truncates_backend(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    old_run = log_root / "dev" / "20260701_100000"
    latest_run = log_root / "dev" / "20260702_100000"
    write(old_run / "api.stderr.log", "OLD")
    write(latest_run / "state.json", "{}")
    write(log_root / "backend.log", "BACKEND")

    run_script(log_root, "--keep-days", "0")

    assert not old_run.exists()
    assert latest_run.is_dir()
    assert (log_root / "backend.log").read_text(encoding="utf-8") == ""


def test_protected_histories_are_never_selected(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    write(log_root / "BugReport.log")
    write(log_root / "bugreport_screenshots" / "capture.png")
    write(log_root / "catalogs" / "detail.log")
    write(log_root / "worker_market.log")

    plan = build_cleanup_plan(log_root=log_root, keep_days=0)
    selected = {target["path"] for target in plan["targets"]}

    assert "worker_market.log" in selected
    assert "BugReport.log" not in selected
    assert "bugreport_screenshots/capture.png" not in selected
    assert "catalogs/detail.log" not in selected


def test_configured_active_run_is_protected_even_when_latest_is_included(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_root = tmp_path / "logs"
    active_run = log_root / "dev" / "20260701_100000"
    latest_run = log_root / "dev" / "20260702_100000"
    write(active_run / "api.stderr.log")
    write(latest_run / "state.json", "{}")
    monkeypatch.setenv("GROWEN_DEV_RUN_LOG_DIR", str(active_run))

    plan = build_cleanup_plan(log_root=log_root, keep_days=0, preserve_latest_dev_run=False)
    selected = {target["path"] for target in plan["targets"]}

    assert "dev/20260701_100000" not in {path.replace("\\", "/") for path in selected}
    assert "dev/20260702_100000" in {path.replace("\\", "/") for path in selected}


def test_executor_rejects_paths_outside_log_root(tmp_path: Path) -> None:
    log_root = tmp_path / "logs"
    log_root.mkdir()
    outside = tmp_path / "outside.log"
    write(outside)
    plan = {"log_root": str(log_root), "targets": [{"path": "../outside.log", "kind": "file", "size_bytes": 3}], "protected": []}

    result = execute_cleanup_plan(plan)

    assert result["ok"] is False
    assert outside.exists()
