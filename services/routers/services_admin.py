from __future__ import annotations

"""Admin services control endpoints (start/stop/status/logs).

Security: admin/colaborador only for mutating actions.
"""

import os
import socket
import time
import uuid
from typing import Any, Dict, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_session
from db.models import Service, ServiceLog
from services.auth import require_roles, require_csrf
from services.orchestrator import start_service as _start, stop_service as _stop, status_service as _status


router = APIRouter(prefix="/admin/services", tags=["admin","services"])

# Define known non-core services (core stays always available at boot)
KNOWN_SERVICES = [
    "pdf_import",
    "playwright",
    "image_processing",
    "dramatiq",
    "scheduler",
    "tiendanube",
    "notifier",
]


def _cid() -> str:
    return uuid.uuid4().hex


async def _ensure_row(db: AsyncSession, name: str) -> Service:
    row = await db.scalar(select(Service).where(Service.name == name))
    if row:
        return row
    row = Service(name=name, status="stopped", auto_start=False)
    db.add(row)
    await db.flush()
    return row


@router.get("", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def list_services(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    # Ensure known services exist so UI always shows a complete list
    for name in KNOWN_SERVICES:
        await _ensure_row(db, name)
    await db.commit()
    rows = (await db.execute(select(Service))).scalars().all()
    items = [
        {
            "id": r.id,
            "name": r.name,
            "status": r.status,
            "auto_start": r.auto_start,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            # If running and started_at set, compute live uptime; else show stored uptime_s
            "uptime_s": (int((datetime.utcnow() - r.started_at).total_seconds()) if (r.status == "running" and r.started_at) else (r.uptime_s or 0)),
            "start_ms": (r.meta or {}).get("last_start_ms") if isinstance(r.meta, dict) else None,
            "last_error": r.last_error,
        }
        for r in rows
    ]
    return {"items": items}


@router.patch("/{name}", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def update_service(name: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    row = await _ensure_row(db, name)
    changed = False
    if "auto_start" in payload:
        row.auto_start = bool(payload["auto_start"])
        changed = True
    if changed:
        await db.commit()
    return {"name": name, "auto_start": row.auto_start}


@router.get("/{name}/status", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def status(name: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    row = await _ensure_row(db, name)
    st = _status(name)
    row.status = st.status
    # If stopped, store final uptime and clear started_at
    if st.status != "running":
        if row.started_at:
            try:
                row.uptime_s = int((datetime.utcnow() - row.started_at).total_seconds())
            except Exception:
                pass
        row.started_at = None
    await db.commit()
    return {"name": name, "status": st.status, "detail": st.detail}


@router.post("/{name}/start", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def start(name: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    row = await _ensure_row(db, name)
    cid = _cid()
    t0 = time.perf_counter()
    try:
        st = _start(name, correlation_id=cid)
        dur = int((time.perf_counter() - t0) * 1000)
        row.status = st.status
        if st.ok:
            row.started_at = datetime.utcnow()
            row.uptime_s = 0
            # persist last start duration in meta
            meta = (row.meta or {}) if isinstance(row.meta, dict) else {}
            meta["last_start_ms"] = dur
            row.meta = meta
            row.last_error = None
        else:
            row.last_error = (st.detail or "")[:500]
        db.add(ServiceLog(service=name, correlation_id=cid, action="start", host=socket.gethostname(), pid=None, duration_ms=dur, ok=st.ok, level=("INFO" if st.ok else "ERROR"), error=(None if st.ok else st.detail), payload={"detail": st.detail}))
        await db.commit()
        return {"name": name, "status": st.status, "ok": st.ok, "correlation_id": cid, "detail": st.detail}
    except Exception as e:
        db.add(ServiceLog(service=name, correlation_id=cid, action="start", host=socket.gethostname(), pid=None, duration_ms=None, ok=False, level="ERROR", error=str(e)))
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/stop", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def stop(name: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    await _ensure_row(db, name)
    cid = _cid()
    t0 = time.perf_counter()
    st = _stop(name, correlation_id=cid)
    dur = int((time.perf_counter() - t0) * 1000)
    # update persisted uptime and clear started_at
    row = await _ensure_row(db, name)
    if row.started_at:
        try:
            row.uptime_s = int((datetime.utcnow() - row.started_at).total_seconds())
        except Exception:
            pass
    row.started_at = None
    row.status = st.status
    db.add(ServiceLog(service=name, correlation_id=cid, action="stop", host=socket.gethostname(), pid=None, duration_ms=dur, ok=st.ok, level=("INFO" if st.ok else "ERROR"), error=(None if st.ok else st.detail), payload={"detail": st.detail}))
    await db.commit()
    return {"name": name, "status": st.status, "ok": st.ok, "correlation_id": cid, "detail": st.detail}


@router.post("/panic-stop", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def panic_stop(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for name in KNOWN_SERVICES:
        cid = _cid()
        st = _stop(name, correlation_id=cid)
        db.add(ServiceLog(service=name, correlation_id=cid, action="stop", host=socket.gethostname(), pid=None, duration_ms=None, ok=st.ok, level=("INFO" if st.ok else "ERROR"), error=(None if st.ok else st.detail), payload={"detail": st.detail}))
        out.append({"name": name, "status": st.status, "ok": st.ok, "correlation_id": cid})
    await db.commit()
    return {"stopped": out}


@router.get("/{name}/logs", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def tail_logs(name: str, tail: int = Query(100, ge=1, le=1000), db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    rows = (await db.execute(select(ServiceLog).where(ServiceLog.service == name).order_by(ServiceLog.created_at.desc()).limit(tail))).scalars().all()
    items = [
        {
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            "service": r.service,
            "action": r.action,
            "cid": r.correlation_id,
            "ok": r.ok,
            "level": r.level,
            "error": r.error,
            "payload": r.payload,
        }
        for r in rows
    ]
    return {"items": items}


@router.get("/{name}/logs/stream", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def stream_logs(name: str, db: AsyncSession = Depends(get_session), last_id: int = Query(0, ge=0), poll_ms: int = Query(1000, ge=200, le=10_000)):
    async def event_gen():  # type: ignore
        import json
        import asyncio
        from sqlalchemy import select

        nonlocal last_id
        try:
            while True:
                rows = (await db.execute(
                    select(ServiceLog)
                    .where(ServiceLog.service == name, ServiceLog.id > last_id)
                    .order_by(ServiceLog.id.asc())
                    .limit(500)
                )).scalars().all()
                if rows:
                    for r in rows:
                        last_id = max(last_id, r.id)
                        payload = {
                            "id": r.id,
                            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                            "action": r.action,
                            "ok": r.ok,
                            "level": r.level,
                            "error": r.error,
                            "payload": r.payload,
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                else:
                    # keepalive
                    yield "event: ping\n\n"
                await asyncio.sleep(poll_ms / 1000)
        except asyncio.CancelledError:  # pragma: no cover
            return

    return StreamingResponse(event_gen(), media_type="text/event-stream")
