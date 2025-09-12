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
    """Return True only if Docker CLI exists AND the engine is reachable.

    On some hosts (e.g., Windows with Docker Desktop stopped) the `docker`
    binary is present but the engine socket isn't. In that case, trying to
    run `docker compose` will fail with errors like:
      - open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
      - Cannot connect to the Docker daemon

    To avoid surfacing these failures to the UI, proactively check engine
    health via `docker info` with a short timeout. If it fails, behave as if
    Docker isn't available and fall back to the lazy in-process registry.
    """
    if not (shutil.which("docker") and COMPOSE_FILE.exists()):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info", "-f", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode != 0:
            return False
        return bool((proc.stdout or "").strip())
    except Exception:
        return False


def _compose(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")


def start_service(name: str, correlation_id: str) -> ServiceStatus:
    if _has_docker():
        # Idempotencia amable: si ya está en running/starting, no intentes reiniciar
        current = status_service(name)
        if current.status in ("running", "starting"):
            return ServiceStatus(name=name, status=current.status, ok=True, detail=f"noop: already {current.status}")
        proc = _compose(["up", "-d", name])
        ok = proc.returncode == 0
        detail = proc.stdout.strip() or proc.stderr.strip()
        # Después de up, consultar rápidamente el estado para normalizar running/starting
        post = status_service(name)
        status = post.status if post.status else ("running" if ok else "failed")
        return ServiceStatus(name=name, status=status, ok=ok, detail=detail)
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
        lower = out.lower()
        ok = proc.returncode == 0
        # Normalización flexible de estados de Docker/Compose
        # "Up", "Up (healthy)", "running" => running
        # "health: starting", "restarting", "starting" => starting
        # "unhealthy" => degraded
        # "exited", "stopped" => stopped
        status = "stopped"
        if any(k in lower for k in ("unhealthy",)):
            status = "degraded"
        if any(k in lower for k in ("health: starting", "restarting", "starting")):
            status = "starting"
        if ok and any(k in lower for k in ("up", "running", "started", "healthy")) and "health: starting" not in lower:
            status = "running"
        return ServiceStatus(name=name, status=status, ok=True, detail=out.strip())
    st = _LAZY_STATE.get(name, "stopped")
    return ServiceStatus(name=name, status=st, ok=True, detail="lazy-status (no docker)")
