from __future__ import annotations

# NG-HEADER: Nombre de archivo: backups_admin.py
# NG-HEADER: Ubicación: services/routers/backups_admin.py
# NG-HEADER: Descripción: Endpoints admin para gestionar backups (listar, crear, descargar) y chequeo automático diario.
# NG-HEADER: Lineamientos: Ver AGENTS.md

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from services.auth import require_roles, require_csrf
from services.backups import list_backups, make_backup, latest_backup_age_hours, BACKUPS_DIR
import json


router = APIRouter(prefix="/admin/backups", tags=["admin", "backups"])


@router.get("", dependencies=[Depends(require_roles("admin"))])
async def list_all() -> Dict[str, Any]:
    """Lista backups disponibles ordenados por fecha (desc)."""
    return {"items": list_backups()}


@router.post("/run", dependencies=[Depends(require_roles("admin")), Depends(require_csrf)])
async def run_backup() -> Dict[str, Any]:
    """Ejecuta un backup inmediato y devuelve metadatos del resultado."""
    db_url = os.getenv("DB_URL") or ""
    if not db_url:
        raise HTTPException(status_code=400, detail="DB_URL no configurada")
    meta = make_backup(db_url)
    if not meta.get("ok"):
        raise HTTPException(status_code=500, detail=meta.get("stderr") or meta.get("stdout") or "Backup falló")
    return {"detail": "ok", "meta": meta}


@router.get("/download/{filename}", dependencies=[Depends(require_roles("admin"))])
async def download_backup(filename: str):
    """Descarga un archivo de backup existente por nombre de archivo."""
    # Seguridad básica: evitar path traversal
    if "/" in filename or ".." in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="filename inválido")
    path = BACKUPS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="No encontrado")
    return FileResponse(str(path), filename=filename, media_type="application/octet-stream")


def ensure_daily_backup_on_boot() -> dict:
    """Si no hay backup de las últimas 24h, ejecuta uno en el arranque.

    Devuelve un dict con la decisión tomada (skipped/run) y timestamp UTC.
    """
    now = datetime.now(timezone.utc).isoformat()
    age_h = latest_backup_age_hours()
    if age_h is not None and age_h < 24.0:
        meta = {"action": "skipped", "age_h": round(age_h, 2), "at": now}
        _persist_last_auto(meta)
        return meta
    db_url = os.getenv("DB_URL") or ""
    if not db_url:
        meta = {"action": "skipped", "reason": "no_db_url", "at": now}
        _persist_last_auto(meta)
        return meta
    meta = make_backup(db_url, prefix="auto")
    result = {"action": "run", "ok": meta.get("ok"), "file": meta.get("file"), "at": now}
    _persist_last_auto(result)
    return result


LAST_AUTO_FILE = BACKUPS_DIR.parent / ".last_auto.json"

def _persist_last_auto(data: dict) -> None:
    try:
        LAST_AUTO_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_AUTO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def _load_last_auto() -> dict:
    try:
        with open(LAST_AUTO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@router.get("/last-auto", dependencies=[Depends(require_roles("admin"))])
async def last_auto_backup() -> Dict[str, Any]:
    """Devuelve metadata del último chequeo/ejecución de autobackup (persistido en archivo)."""
    return {"meta": _load_last_auto()}
