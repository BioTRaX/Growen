# NG-HEADER: Nombre de archivo: orchestrator.py
# NG-HEADER: Ubicación: services/orchestrator.py
# NG-HEADER: Descripción: Orquesta servicios locales y Docker con dependencias verificables.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

"""Lightweight orchestrator for service containers (dev) with lazy fallback.

In dev, tries to control services via `docker compose` using the project's
docker-compose.yml. If Docker is unavailable, falls back to a simple in-process
"lazy" registry so the API can simulate start/stop/status for UI flows.
"""

import os
import socket
import shutil
import subprocess
import time
import psutil
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
_MARKET_WORKER_PROC: Optional[subprocess.Popen] = None  # Track market_worker process
_DRIVE_SYNC_WORKER_PROC: Optional[subprocess.Popen] = None  # Track drive_sync_worker process
_DRIVE_SYNC_WORKER_MODE: Optional[str] = None  # Track mode: 'docker' or 'local'
_TELEGRAM_POLLING_WORKER_PROC: Optional[subprocess.Popen] = None  # Track telegram_polling_worker process
_CATALOG_WORKER_PROC: Optional[subprocess.Popen] = None  # Track catalog_worker process


def _has_docker() -> bool:
    """Return True only if Docker CLI exists AND the engine is reachable.

    On some hosts (e.g., Windows with Docker Desktop stopped) the `docker`
    binary is present but the engine socket isn't. In that case, trying to
    run `docker compose` will fail with errors like:
      - open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
      - Cannot connect to the Docker daemon

    To avoid surfacing these failures to the UI, proactively check engine
    health via `docker info` with a bounded timeout. Docker Desktop on Windows
    can legitimately need several seconds to answer even when containers are
    healthy, so the timeout is configurable and defaults to eight seconds. If it fails, behave as if
    Docker isn't available and fall back to the lazy in-process registry.
    """
    if not (shutil.which("docker") and COMPOSE_FILE.exists()):
        return False
    try:
        timeout_s = max(1.0, float(os.getenv("DOCKER_PROBE_TIMEOUT_S", "8")))
        proc = subprocess.run(
            ["docker", "info", "-f", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
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


def _tcp_port_open(host: str, port: int, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_local_redis(timeout_s: float = 15.0) -> tuple[bool, str]:
    """Garantiza el broker host requerido antes de iniciar un worker local."""
    if _tcp_port_open("127.0.0.1", 6379):
        return True, "Redis ya disponible en 127.0.0.1:6379"
    if not _has_docker():
        return False, "Redis no está disponible y Docker no puede iniciarlo"

    proc = _compose(["--profile", "optional", "up", "-d", "redis"])
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "docker compose falló").strip()
        return False, f"No se pudo iniciar Redis: {detail[:300]}"

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _tcp_port_open("127.0.0.1", 6379):
            return True, "Redis iniciado mediante Docker Compose"
        time.sleep(0.25)
    return False, "Redis inició en Compose pero no publicó 127.0.0.1:6379"


def _start_process_with_log(command: list[str], log_name: str) -> tuple[subprocess.Popen, Path]:
    """Inicia un proceso sin pipes huérfanos y conserva stdout/stderr en un archivo."""
    log_path = ROOT / "logs" / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
    finally:
        log_stream.close()
    return process, log_path


def start_service(name: str, correlation_id: str, mode: Optional[str] = None) -> ServiceStatus:
    """Inicia un servicio.
    
    Args:
        name: Nombre del servicio
        correlation_id: ID de correlación para logging
        mode: Modo de ejecución ('docker' o 'local'), solo aplica a drive_sync_worker
    """
    global _MARKET_WORKER_PROC, _DRIVE_SYNC_WORKER_PROC, _DRIVE_SYNC_WORKER_MODE, _TELEGRAM_POLLING_WORKER_PROC, _CATALOG_WORKER_PROC
    
    # Manejo especial para drive_sync_worker (puede ser Docker o Local)
    if name == "drive_sync_worker":
        # Si no se especifica modo, usar Docker si está disponible, sino Local
        if mode is None:
            mode = "docker" if _has_docker() else "local"
        _DRIVE_SYNC_WORKER_MODE = mode
        
        current = status_service(name)
        if current.status == "running":
            return ServiceStatus(name=name, status="running", ok=True, detail=f"noop: already running ({mode})")
        
        if mode == "docker":
            # Iniciar contenedor Docker
            if not _has_docker():
                return ServiceStatus(name=name, status="failed", ok=False, detail="Docker no disponible")
            proc = _compose(["up", "-d", "dramatiq"])
            ok = proc.returncode == 0
            detail = proc.stdout.strip() or proc.stderr.strip()
            if ok:
                detail = f"Docker container started ({detail})"
            return ServiceStatus(name=name, status=("running" if ok else "failed"), ok=ok, detail=detail)
        else:
            # Modo local: ejecutar script
            script_path = ROOT / "scripts" / "start_worker_drive_sync.cmd"
            if not script_path.exists():
                return ServiceStatus(name=name, status="failed", ok=False, detail="Script not found")
            
            try:
                # Ejecutar el script en background
                _DRIVE_SYNC_WORKER_PROC = subprocess.Popen(
                    [str(script_path)],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                return ServiceStatus(name=name, status="running", ok=True, detail=f"Local worker started with PID {_DRIVE_SYNC_WORKER_PROC.pid}")
            except Exception as e:
                return ServiceStatus(name=name, status="failed", ok=False, detail=str(e))
    
    # Worker Mercado: contenedor dedicado con Chromium.
    if name == "market_worker":
        current = status_service(name)
        if current.status == "running":
            return ServiceStatus(name=name, status="running", ok=True, detail="noop: already running")
        if not _has_docker():
            return ServiceStatus(name=name, status="failed", ok=False, detail="Docker no disponible")
        redis_ok, redis_detail = _ensure_local_redis()
        if not redis_ok:
            return ServiceStatus(name=name, status="failed", ok=False, detail=redis_detail)
        proc = _compose(["--profile", "optional", "up", "-d", "--build", "--no-deps", "market_worker"])
        ok = proc.returncode == 0
        detail = (proc.stdout or proc.stderr or "docker compose sin salida").strip()
        return ServiceStatus(name=name, status="running" if ok else "failed", ok=ok, detail=detail[-1000:])
        
        script_path = ROOT / "scripts" / "start_worker_market.cmd"
        if not script_path.exists():
            return ServiceStatus(name=name, status="failed", ok=False, detail="Script not found")
        
        try:
            # Ejecutar el script en background
            _MARKET_WORKER_PROC = subprocess.Popen(
                [str(script_path)],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Started with PID {_MARKET_WORKER_PROC.pid}")
        except Exception as e:
            return ServiceStatus(name=name, status="failed", ok=False, detail=str(e))
    
    # Manejo especial para telegram_polling_worker (proceso local, no Docker)
    if name == "telegram_polling_worker":
        current = status_service(name)
        if current.status == "running":
            return ServiceStatus(name=name, status="running", ok=True, detail="noop: already running")
        
        script_path = ROOT / "scripts" / "start_worker_telegram_polling.cmd"
        if not script_path.exists():
            return ServiceStatus(name=name, status="failed", ok=False, detail="Script not found")
        
        try:
            # Ejecutar el script en background
            _TELEGRAM_POLLING_WORKER_PROC = subprocess.Popen(
                [str(script_path)],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Started with PID {_TELEGRAM_POLLING_WORKER_PROC.pid}")
        except Exception as e:
            return ServiceStatus(name=name, status="failed", ok=False, detail=str(e))
    
    # Manejo especial para catalog_worker (proceso local, no Docker)
    if name == "catalog_worker":
        current = status_service(name)
        if current.status == "running":
            return ServiceStatus(name=name, status="running", ok=True, detail="noop: already running")

        redis_ok, redis_detail = _ensure_local_redis()
        if not redis_ok:
            return ServiceStatus(name=name, status="failed", ok=False, detail=redis_detail)
        
        script_path = ROOT / "scripts" / "start_worker_catalog.cmd"
        if not script_path.exists():
            return ServiceStatus(name=name, status="failed", ok=False, detail="Script not found")
        
        try:
            _CATALOG_WORKER_PROC, log_path = _start_process_with_log(
                [str(script_path)],
                "worker_catalog.log",
            )
            return ServiceStatus(
                name=name,
                status="running",
                ok=True,
                detail=f"{redis_detail}; worker iniciado con PID {_CATALOG_WORKER_PROC.pid}; log: {log_path}",
            )
        except Exception as e:
            return ServiceStatus(name=name, status="failed", ok=False, detail=str(e))
    
    # Lógica original para servicios Docker
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
    global _MARKET_WORKER_PROC, _DRIVE_SYNC_WORKER_PROC, _DRIVE_SYNC_WORKER_MODE, _TELEGRAM_POLLING_WORKER_PROC, _CATALOG_WORKER_PROC
    
    # Manejo especial para drive_sync_worker
    if name == "drive_sync_worker":
        mode = _DRIVE_SYNC_WORKER_MODE or "local"
        
        if mode == "docker":
            # Detener contenedor Docker
            if _has_docker():
                proc = _compose(["stop", "dramatiq"])
                ok = proc.returncode == 0
                detail = proc.stdout.strip() or proc.stderr.strip()
                if ok:
                    _DRIVE_SYNC_WORKER_MODE = None
                return ServiceStatus(name=name, status=("stopped" if ok else "failed"), ok=ok, detail=detail)
            _DRIVE_SYNC_WORKER_MODE = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail="Docker not available")
        else:
            # Modo local: terminar proceso
            if _DRIVE_SYNC_WORKER_PROC is None or _DRIVE_SYNC_WORKER_PROC.poll() is not None:
                # Buscar por nombre de proceso como fallback
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            cmdline = proc.info.get('cmdline', [])
                            if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'drive_sync' in ' '.join(cmdline).lower():
                                proc.terminate()
                                proc.wait(timeout=5)
                                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {proc.info['pid']}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    return ServiceStatus(name=name, status="stopped", ok=True, detail="Process not found (already stopped)")
                except Exception as e:
                    return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Error finding process: {e}")
            
            # Terminar proceso conocido
            try:
                _DRIVE_SYNC_WORKER_PROC.terminate()
                _DRIVE_SYNC_WORKER_PROC.wait(timeout=5)
                pid = _DRIVE_SYNC_WORKER_PROC.pid
                _DRIVE_SYNC_WORKER_PROC = None
                _DRIVE_SYNC_WORKER_MODE = None
                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {pid}")
            except Exception as e:
                _DRIVE_SYNC_WORKER_PROC = None
                _DRIVE_SYNC_WORKER_MODE = None
                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Force terminated: {e}")
    
    # Manejo especial para market_worker
    if name == "market_worker":
        if _has_docker():
            proc = _compose(["--profile", "optional", "stop", "market_worker"])
            ok = proc.returncode == 0
            return ServiceStatus(
                name=name,
                status="stopped" if ok else "failed",
                ok=ok,
                detail=(proc.stdout or proc.stderr or "docker compose sin salida").strip()[-1000:],
            )
        if _MARKET_WORKER_PROC is None or _MARKET_WORKER_PROC.poll() is not None:
            # Proceso no existe o ya terminó
            # Buscar por nombre de proceso como fallback
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'market_scraping' in ' '.join(cmdline).lower():
                            proc.terminate()
                            proc.wait(timeout=5)
                            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return ServiceStatus(name=name, status="stopped", ok=True, detail="Process not found (already stopped)")
            except Exception as e:
                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Error finding process: {e}")
        
        # Terminar proceso conocido
        try:
            _MARKET_WORKER_PROC.terminate()
            _MARKET_WORKER_PROC.wait(timeout=5)
            pid = _MARKET_WORKER_PROC.pid
            _MARKET_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {pid}")
        except Exception as e:
            _MARKET_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Force terminated: {e}")
    
    # Manejo especial para telegram_polling_worker
    if name == "telegram_polling_worker":
        if _TELEGRAM_POLLING_WORKER_PROC is None or _TELEGRAM_POLLING_WORKER_PROC.poll() is not None:
            # Proceso no existe o ya terminó
            # Buscar por nombre de proceso como fallback
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'telegram_polling' in ' '.join(cmdline).lower():
                            proc.terminate()
                            proc.wait(timeout=5)
                            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return ServiceStatus(name=name, status="stopped", ok=True, detail="Process not found (already stopped)")
            except Exception as e:
                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Error finding process: {e}")
        
        # Terminar proceso conocido
        try:
            _TELEGRAM_POLLING_WORKER_PROC.terminate()
            _TELEGRAM_POLLING_WORKER_PROC.wait(timeout=5)
            pid = _TELEGRAM_POLLING_WORKER_PROC.pid
            _TELEGRAM_POLLING_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {pid}")
        except Exception as e:
            _TELEGRAM_POLLING_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Force terminated: {e}")
    
    # Manejo especial para catalog_worker
    if name == "catalog_worker":
        if _CATALOG_WORKER_PROC is None or _CATALOG_WORKER_PROC.poll() is not None:
            # Proceso no existe o ya terminó
            # Buscar por nombre de proceso como fallback
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'catalog_jobs' in ' '.join(cmdline).lower():
                            proc.terminate()
                            proc.wait(timeout=5)
                            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return ServiceStatus(name=name, status="stopped", ok=True, detail="Process not found (already stopped)")
            except Exception as e:
                return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Error finding process: {e}")
        
        # Terminar proceso conocido
        try:
            _CATALOG_WORKER_PROC.terminate()
            _CATALOG_WORKER_PROC.wait(timeout=5)
            pid = _CATALOG_WORKER_PROC.pid
            _CATALOG_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Terminated PID {pid}")
        except Exception as e:
            _CATALOG_WORKER_PROC = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail=f"Force terminated: {e}")
    
    # Lógica original para servicios Docker
    if _has_docker():
        proc = _compose(["stop", name])
        ok = proc.returncode == 0
        detail = proc.stdout.strip() or proc.stderr.strip()
        return ServiceStatus(name=name, status=("stopped" if ok else "failed"), ok=ok, detail=detail)
    _LAZY_STATE[name] = "stopped"
    return ServiceStatus(name=name, status="stopped", ok=True, detail="lazy-stop (no docker)")


def status_service(name: str) -> ServiceStatus:
    global _MARKET_WORKER_PROC, _DRIVE_SYNC_WORKER_PROC, _DRIVE_SYNC_WORKER_MODE, _TELEGRAM_POLLING_WORKER_PROC, _CATALOG_WORKER_PROC
    
    # Manejo especial para drive_sync_worker
    if name == "drive_sync_worker":
        # Detectar modo: primero verificar Docker, luego local
        docker_running = False
        if _has_docker():
            proc = _compose(["ps", "dramatiq"])
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            lower = out.lower()
            docker_running = proc.returncode == 0 and any(k in lower for k in ("up", "running", "started", "healthy")) and "health: starting" not in lower
        
        local_running = False
        local_pid = None
        if _DRIVE_SYNC_WORKER_PROC is not None and _DRIVE_SYNC_WORKER_PROC.poll() is None:
            local_running = True
            local_pid = _DRIVE_SYNC_WORKER_PROC.pid
        else:
            # Buscar en procesos del sistema
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'drive_sync' in ' '.join(cmdline).lower():
                            local_running = True
                            local_pid = proc.info['pid']
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        
        # Determinar modo y estado
        if docker_running:
            # Docker está corriendo
            if not _DRIVE_SYNC_WORKER_MODE:
                _DRIVE_SYNC_WORKER_MODE = "docker"
            proc = _compose(["ps", "dramatiq"])
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            lower = out.lower()
            status = "stopped"
            if any(k in lower for k in ("unhealthy",)):
                status = "degraded"
            if any(k in lower for k in ("health: starting", "restarting", "starting")):
                status = "starting"
            if any(k in lower for k in ("up", "running", "started", "healthy")) and "health: starting" not in lower:
                status = "running"
            return ServiceStatus(name=name, status=status, ok=True, detail=f"Docker mode ({out.strip()[:100]})")
        elif local_running:
            # Local está corriendo
            if not _DRIVE_SYNC_WORKER_MODE:
                _DRIVE_SYNC_WORKER_MODE = "local"
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Local mode - PID {local_pid}")
        else:
            # No está corriendo en ningún modo
            _DRIVE_SYNC_WORKER_MODE = None
            return ServiceStatus(name=name, status="stopped", ok=True, detail="Not running")
    
    # Manejo especial para market_worker
    if name == "market_worker":
        if _has_docker():
            proc = _compose(["--profile", "optional", "ps", "market_worker"])
            output = (proc.stdout or proc.stderr or "").lower()
            running = proc.returncode == 0 and any(token in output for token in ("running", "up", "healthy"))
            if "unhealthy" in output:
                status = "degraded"
            elif any(token in output for token in ("starting", "restarting")):
                status = "starting"
            else:
                status = "running" if running else "stopped"
            return ServiceStatus(
                name=name,
                status=status,
                ok=status not in {"degraded"},
                detail=(proc.stdout or proc.stderr or "Not running").strip()[-1000:],
            )
        # Verificar proceso global primero
        if _MARKET_WORKER_PROC is not None and _MARKET_WORKER_PROC.poll() is None:
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {_MARKET_WORKER_PROC.pid}")
        
        # Buscar en procesos del sistema
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'market_scraping' in ' '.join(cmdline).lower():
                        return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ServiceStatus(name=name, status="stopped", ok=True, detail="Not running")
    
    # Manejo especial para telegram_polling_worker
    if name == "telegram_polling_worker":
        # Verificar proceso global primero
        if _TELEGRAM_POLLING_WORKER_PROC is not None and _TELEGRAM_POLLING_WORKER_PROC.poll() is None:
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {_TELEGRAM_POLLING_WORKER_PROC.pid}")
        
        # Buscar en procesos del sistema
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'telegram_polling' in ' '.join(cmdline).lower():
                        return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ServiceStatus(name=name, status="stopped", ok=True, detail="Not running")
    
    # Manejo especial para catalog_worker
    if name == "catalog_worker":
        # Verificar proceso global primero
        if _CATALOG_WORKER_PROC is not None and _CATALOG_WORKER_PROC.poll() is None:
            return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {_CATALOG_WORKER_PROC.pid}")
        
        # Buscar en procesos del sistema
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and 'dramatiq' in ' '.join(cmdline).lower() and 'catalog_jobs' in ' '.join(cmdline).lower():
                        return ServiceStatus(name=name, status="running", ok=True, detail=f"Running PID {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ServiceStatus(name=name, status="stopped", ok=True, detail="Not running")
    
    # Lógica original para servicios Docker
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
