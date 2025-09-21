from __future__ import annotations

# NG-HEADER: Nombre de archivo: backups.py
# NG-HEADER: Ubicación: services/backups.py
# NG-HEADER: Descripción: Utilidades para generar y listar backups de la base de datos PostgreSQL.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
BACKUPS_DIR = ROOT / "backups" / "pg"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DBConn:
    user: str
    password: str
    host: str
    port: int
    dbname: str


def parse_db_url(db_url: str) -> DBConn:
    url = make_url(db_url)
    return DBConn(
        user=str(url.username or ""),
        password=str(url.password or ""),
        host=str(url.host or "localhost"),
        port=int(url.port or 5432),
        dbname=str(url.database or "postgres"),
    )


def _has_docker() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info", "-f", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return proc.returncode == 0 and bool((proc.stdout or "").strip())
    except Exception:
        return False


def _container_exists(name: str) -> bool:
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=5
        )
        if proc.returncode != 0:
            return False
        names = (proc.stdout or "").splitlines()
        return name in names
    except Exception:
        return False


def list_backups() -> List[dict]:
    items: List[dict] = []
    try:
        for p in sorted(BACKUPS_DIR.glob("*.dump")):
            try:
                stat = p.stat()
                items.append(
                    {
                        "filename": p.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "path": str(p),
                    }
                )
            except Exception:
                continue
    except Exception:
        pass
    # Orden descendente por fecha
    items.sort(key=lambda x: x.get("modified") or "", reverse=True)
    return items


def latest_backup_age_hours() -> Optional[float]:
    items = list_backups()
    if not items:
        return None
    try:
        last_iso = items[0]["modified"]
        last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
        return age
    except Exception:
        return None


def _run_host_pg_dump(db: DBConn, out_file: Path) -> subprocess.CompletedProcess:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise FileNotFoundError("pg_dump no encontrado en PATH")
    env = os.environ.copy()
    if db.password:
        env["PGPASSWORD"] = db.password
    cmd = [
        pg_dump,
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.dbname,
        "-Fc",
        "-f",
        str(out_file),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _run_docker_pg_dump(container: str, db: DBConn, out_file: Path) -> subprocess.CompletedProcess:
    # Crear en /tmp del contenedor y luego copiar al host
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_path = f"/tmp/{out_file.stem}-{ts}.dump"
    # Usar env inline para PGPASSWORD
    inline = [
        "docker",
        "exec",
        container,
        "bash",
        "-lc",
        f"PGPASSWORD='{db.password}' pg_dump -U {db.user} -d {db.dbname} -Fc -f {tmp_path}",
    ]
    proc_dump = subprocess.run(inline, capture_output=True, text=True)
    if proc_dump.returncode != 0:
        return proc_dump
    # Copiar al host
    proc_cp = subprocess.run(["docker", "cp", f"{container}:{tmp_path}", str(out_file)], capture_output=True, text=True)
    # Best-effort limpieza en contenedor
    try:
        subprocess.run(["docker", "exec", container, "rm", "-f", tmp_path], capture_output=True, text=True)
    except Exception:
        pass
    return proc_cp


def make_backup(db_url: str, container_name: str = "growen-postgres", prefix: str = "backup") -> dict:
    """Genera un backup (pg_dump -Fc) en BACKUPS_DIR y devuelve metadatos.

    Estrategia:
    - Si hay Docker y existe el contenedor `container_name`, hace docker exec + docker cp.
    - Si no, intenta usar pg_dump del host.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    db = parse_db_url(db_url)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = BACKUPS_DIR / f"{prefix}_{ts}.dump"
    if _has_docker() and _container_exists(container_name):
        proc = _run_docker_pg_dump(container_name, db, outfile)
    else:
        proc = _run_host_pg_dump(db, outfile)
    ok = proc.returncode == 0
    meta = {
        "ok": ok,
        "file": outfile.name,
        "path": str(outfile),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    # Si falló, borrar archivo vacío/dañado
    if not ok:
        try:
            if outfile.exists():
                outfile.unlink()
        except Exception:
            pass
    else:
        # Rotación simple: mantener últimos N backups (por fecha). Default N=7
        try:
            keep = int(os.getenv("BACKUPS_KEEP_COUNT", "7"))
        except Exception:
            keep = 7
        if keep > 0:
            try:
                items = list_backups()
                # Excluir el recién creado del conteo? No, lista ya incluye el nuevo; dejar los N más recientes
                to_delete = items[keep:]
                for it in to_delete:
                    p = Path(it.get("path") or "")
                    if p.is_file():
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except Exception:
                pass
    return meta
