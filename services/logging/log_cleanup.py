# NG-HEADER: Nombre de archivo: log_cleanup.py
# NG-HEADER: Ubicación: services/logging/log_cleanup.py
# NG-HEADER: Descripción: Inventario y limpieza segura de logs físicos, incluidos los directorios por ejecución de desarrollo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_ROOT = PROJECT_ROOT / "logs"
DEV_RUN_PATTERN = re.compile(r"^\d{8}_\d{6}$")
PROTECTED_DIRECTORIES = {"bugreport_screenshots", "catalog", "catalogs"}


@dataclass(frozen=True)
class CleanupTarget:
    path: str
    kind: Literal["file", "directory", "truncate"]
    size_bytes: int
    reason: str


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not process:
                return False
            ctypes.windll.kernel32.CloseHandle(process)
            return True
        except Exception:
            return False
    return Path(f"/proc/{pid}").exists()


def _active_dev_runs(dev_root: Path) -> set[Path]:
    active: set[Path] = set()
    configured = os.getenv("GROWEN_DEV_RUN_LOG_DIR")
    if configured:
        try:
            active.add(Path(configured).resolve())
        except OSError:
            pass
    if not dev_root.exists():
        return active
    pid_fields = ("api_pid", "frontend_pid", "mcp_products_pid", "mcp_web_search_pid")
    for state_file in dev_root.glob("*/state.json"):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8-sig"))
            if any(_pid_exists(int(state[field])) for field in pid_fields if state.get(field)):
                active.add(state_file.parent.resolve())
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return active


def build_cleanup_plan(
    *,
    log_root: Path = DEFAULT_LOG_ROOT,
    keep_days: int = 0,
    preserve_latest_dev_run: bool = True,
) -> dict[str, object]:
    log_root = log_root.resolve()
    cutoff = time.time() - max(0, keep_days) * 86400
    targets: list[CleanupTarget] = []
    protected: list[dict[str, str]] = []
    dev_root = log_root / "dev"
    run_dirs = sorted(
        (path for path in dev_root.iterdir() if path.is_dir() and DEV_RUN_PATTERN.fullmatch(path.name)),
        key=lambda path: path.name,
    ) if dev_root.exists() else []
    active_runs = _active_dev_runs(dev_root)
    if preserve_latest_dev_run and run_dirs:
        active_runs.add(run_dirs[-1].resolve())

    for run_dir in run_dirs:
        resolved = run_dir.resolve()
        if resolved in active_runs:
            protected.append({"path": str(run_dir.relative_to(log_root)), "reason": "ejecución activa o más reciente"})
            continue
        try:
            if keep_days > 0 and run_dir.stat().st_mtime >= cutoff:
                protected.append({"path": str(run_dir.relative_to(log_root)), "reason": f"retención de {keep_days} días"})
                continue
        except OSError:
            continue
        targets.append(CleanupTarget(str(run_dir.relative_to(log_root)), "directory", _directory_size(run_dir), "ejecución de desarrollo antigua"))

    if log_root.exists():
        for path in log_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(log_root)
            if relative.parts and relative.parts[0] == "dev":
                continue
            if relative.parts and relative.parts[0].lower() in PROTECTED_DIRECTORIES:
                protected.append({"path": str(relative), "reason": "historial protegido por política"})
                continue
            if path.name == "BugReport.log" or path.name.startswith("BugReport.log."):
                protected.append({"path": str(relative), "reason": "historial de reportes protegido"})
                continue
            matches = (
                path.suffix in {".log", ".ndjson"}
                or ".log." in path.name
                or path.name.endswith(".cleared")
                or relative.parts[:1] == ("migrations",)
                or relative.parts[:1] == ("diagnostics",)
            )
            if not matches:
                continue
            try:
                stat = path.stat()
                if keep_days > 0 and stat.st_mtime >= cutoff:
                    protected.append({"path": str(relative), "reason": f"retención de {keep_days} días"})
                    continue
                size = stat.st_size
            except OSError:
                continue
            kind: Literal["file", "directory", "truncate"] = "truncate" if relative == Path("backend.log") else "file"
            targets.append(CleanupTarget(str(relative), kind, size, "log operativo legacy"))

    return {
        "log_root": str(log_root),
        "keep_days": max(0, keep_days),
        "targets": [asdict(target) for target in targets],
        "protected": protected,
        "target_count": len(targets),
        "bytes_reclaimable": sum(target.size_bytes for target in targets),
        "dev_run_directories": sum(target.kind == "directory" for target in targets),
    }


def execute_cleanup_plan(plan: dict[str, object], *, log_root: Path | None = None) -> dict[str, object]:
    root = (log_root or Path(str(plan["log_root"]))).resolve()
    removed_files = 0
    removed_directories = 0
    truncated_files = 0
    bytes_reclaimed = 0
    errors: list[dict[str, str]] = []
    for raw_target in plan.get("targets", []):
        target = dict(raw_target)
        relative = Path(str(target["path"]))
        absolute = (root / relative).resolve()
        try:
            absolute.relative_to(root)
        except ValueError:
            errors.append({"path": str(relative), "error": "ruta fuera del directorio de logs"})
            continue
        try:
            if target["kind"] == "directory":
                if absolute.exists():
                    shutil.rmtree(absolute)
                    removed_directories += 1
            elif target["kind"] == "truncate":
                if absolute.exists():
                    with absolute.open("w", encoding="utf-8"):
                        pass
                    truncated_files += 1
            elif absolute.exists():
                absolute.unlink()
                removed_files += 1
            bytes_reclaimed += int(target.get("size_bytes") or 0)
        except OSError as exc:
            errors.append({"path": str(relative), "error": str(exc)})
    return {
        "ok": not errors,
        "removed_files": removed_files,
        "removed_directories": removed_directories,
        "truncated_files": truncated_files,
        "bytes_reclaimed": bytes_reclaimed,
        "errors": errors,
        "protected": plan.get("protected", []),
    }
