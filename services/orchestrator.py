from __future__ import annotations

"""Lightweight orchestrator for service containers (dev) with lazy fallback.

In dev, tries to control services via `docker compose` using the project's
docker-compose.yml. If Docker is unavailable, falls back to a simple in-process
"lazy" registry so the API can simulate start/stop/status for UI flows.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class ServiceStatus:
    name: str
    status: str  # stopped|starting|running|degraded|failed
    ok: bool
    detail: Optional[str] = None
    pid: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"
_LAZY_STATE: Dict[str, str] = {}


def _has_docker() -> bool:
    return bool(shutil.which("docker")) and COMPOSE_FILE.exists()


def _compose(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")


def start_service(name: str, correlation_id: str) -> ServiceStatus:
    if _has_docker():
        proc = _compose(["up", "-d", name])
        ok = proc.returncode == 0
        detail = proc.stdout.strip() or proc.stderr.strip()
        return ServiceStatus(name=name, status=("running" if ok else "failed"), ok=ok, detail=detail)
    # Fallback: lazy state only
    _LAZY_STATE[name] = "running"
    return ServiceStatus(name=name, status="running", ok=True, detail="lazy-start (no docker)")


def stop_service(name: str, correlation_id: str) -> ServiceStatus:
    if _has_docker():
        proc = _compose(["stop", name])
        ok = proc.returncode == 0
        detail = proc.stdout.strip() or proc.stderr.strip()
        return ServiceStatus(name=name, status=("stopped" if ok else "failed"), ok=ok, detail=detail)
    _LAZY_STATE[name] = "stopped"
    return ServiceStatus(name=name, status="stopped", ok=True, detail="lazy-stop (no docker)")


def status_service(name: str) -> ServiceStatus:
    if _has_docker():
        proc = _compose(["ps", name])
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        running = ("running" in out.lower()) and proc.returncode == 0
        return ServiceStatus(name=name, status=("running" if running else "stopped"), ok=True, detail=out.strip())
    st = _LAZY_STATE.get(name, "stopped")
    return ServiceStatus(name=name, status=st, ok=True, detail="lazy-status (no docker)")

