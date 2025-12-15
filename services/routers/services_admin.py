from __future__ import annotations

# NG-HEADER: Nombre de archivo: services_admin.py
# NG-HEADER: Ubicación: services/routers/services_admin.py
# NG-HEADER: Descripción: Endpoints de administración de servicios (start/stop/status/logs/deps) y health de herramientas.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Admin services control endpoints (start/stop/status/logs).

Security: admin/colaborador only for mutating actions.
"""

import os
import socket
import time
import uuid
import math
from collections import Counter
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.session import get_session
from db.models import Service, ServiceLog, ImportLog, Purchase
from services.auth import require_roles, require_csrf
from services.orchestrator import start_service as _start, stop_service as _stop, status_service as _status
from agent_core.config import settings
import shutil
import subprocess
from services.integrations.notion_client import NotionWrapper, load_notion_settings  # type: ignore


router = APIRouter(prefix="/admin/services", tags=["admin","services"])

# Define known non-core services (core stays always available at boot)
KNOWN_SERVICES = [
    "pdf_import",
    "playwright",
    "image_processing",
    "dramatiq",
    "scheduler",
    "notifier",
    "market_worker",  # Worker de actualización de precios de mercado
    "drive_sync_worker",  # Worker de sincronización Drive
    "telegram_polling_worker",  # Worker de Long Polling para Telegram Bot
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
    """Lista servicios conocidos con estado actual y metadatos.

    Asegura filas para KNOWN_SERVICES y calcula uptime si está en running.
    """
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
    """Actualiza banderas del servicio (ej. auto_start)."""
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
    """Consulta estado del servicio y persiste último estado básico."""
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


@router.get("/pdf_import/metrics", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def pdf_import_metrics(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Métricas agregadas del pipeline de importación de remitos.

    Devuelve:
    - total_imports: compras creadas (purchases) con adjuntos PDF (aprox)
    - avg_classic_confidence: promedio de valores registrados en ImportLog (evento classic_confidence)
    - ai_invocations: conteo de eventos AI request/ok (stage=ai, event=request)
    - ai_success: eventos AI ok
    - ai_success_rate: ai_success / ai_invocations (0 si ai_invocations=0)
    - ai_lines_added: suma de stats merged (event=merged, details.added)
    - last_24h: subconjunto de métricas últimas 24h (mismas claves)
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    # Total imports = purchases creadas último año (heurística) (podríamos filtrar por meta->correlation_id pero no es necesario aquí)
    total_imports = await db.scalar(select(func.count()).select_from(Purchase)) or 0

    # Classic confidence promedio
    classic_rows = (await db.execute(
        select(ImportLog.details).where(ImportLog.event == "classic_confidence")
    )).scalars().all()
    confidences = []
    for d in classic_rows:
        if isinstance(d, dict):
            v = d.get("value")
            try:
                if v is not None:
                    confidences.append(float(v))
            except Exception:
                pass
    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    def _count(stage: str, event: str):
        return db.scalar(select(func.count()).select_from(ImportLog).where(ImportLog.stage==stage, ImportLog.event==event))

    ai_invocations = await db.scalar(select(func.count()).select_from(ImportLog).where(ImportLog.stage=="ai", ImportLog.event=="request")) or 0
    ai_success = await db.scalar(select(func.count()).select_from(ImportLog).where(ImportLog.stage=="ai", ImportLog.event=="ok")) or 0
    ai_success_rate = round(ai_success / ai_invocations, 4) if ai_invocations else 0.0

    merged_rows = (await db.execute(select(ImportLog.details).where(ImportLog.event == "merged"))).scalars().all()
    ai_lines_added = 0
    for d in merged_rows:
        if isinstance(d, dict):
            try:
                ai_lines_added += int(d.get("added") or 0)
            except Exception:
                pass

    # Últimas 24h
    from sqlalchemy import and_
    classic_rows_24 = (await db.execute(
        select(ImportLog.details).where(and_(ImportLog.event=="classic_confidence", ImportLog.created_at >= day_ago))
    )).scalars().all()
    confidences_24 = []
    for d in classic_rows_24:
        if isinstance(d, dict):
            v = d.get("value")
            try:
                if v is not None:
                    confidences_24.append(float(v))
            except Exception:
                pass
    avg_conf_24 = round(sum(confidences_24)/len(confidences_24), 4) if confidences_24 else 0.0
    ai_invocations_24 = await db.scalar(select(func.count()).select_from(ImportLog).where(and_(ImportLog.stage=="ai", ImportLog.event=="request", ImportLog.created_at >= day_ago))) or 0
    ai_success_24 = await db.scalar(select(func.count()).select_from(ImportLog).where(and_(ImportLog.stage=="ai", ImportLog.event=="ok", ImportLog.created_at >= day_ago))) or 0
    ai_success_rate_24 = round(ai_success_24 / ai_invocations_24, 4) if ai_invocations_24 else 0.0
    merged_rows_24 = (await db.execute(select(ImportLog.details).where(and_(ImportLog.event=="merged", ImportLog.created_at >= day_ago)))).scalars().all()
    ai_lines_added_24 = 0
    for d in merged_rows_24:
        if isinstance(d, dict):
            try:
                ai_lines_added_24 += int(d.get("added") or 0)
            except Exception:
                pass

    return {
        "total_imports": total_imports,
        "avg_classic_confidence": avg_conf,
        "ai_invocations": ai_invocations,
        "ai_success": ai_success,
        "ai_success_rate": ai_success_rate,
        "ai_lines_added": ai_lines_added,
        "last_24h": {
            "avg_classic_confidence": avg_conf_24,
            "ai_invocations": ai_invocations_24,
            "ai_success": ai_success_24,
            "ai_success_rate": ai_success_rate_24,
            "ai_lines_added": ai_lines_added_24,
        },
    }

@router.get("/pdf_import/ai_stats", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def pdf_import_ai_stats(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Estadisticas detalladas del fallback IA de importacion de remitos.

    Resume invocaciones, exitos, modelos y latencias tanto globales como en la ventana de 24 horas.
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    async def _count(event: str, since: Optional[datetime] = None) -> int:
        stmt = select(func.count()).select_from(ImportLog).where(ImportLog.stage == "ai", ImportLog.event == event)
        if since is not None:
            stmt = stmt.where(ImportLog.created_at >= since)
        return await db.scalar(stmt) or 0

    async def _details(event: str, since: Optional[datetime] = None) -> List[dict]:
        stmt = select(ImportLog.details).where(ImportLog.stage == "ai", ImportLog.event == event)
        if since is not None:
            stmt = stmt.where(ImportLog.created_at >= since)
        rows = (await db.execute(stmt)).scalars().all()
        return [row for row in rows if isinstance(row, dict)]

    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _to_int(value: Any) -> int:
        try:
            return int(round(float(value)))
        except Exception:
            return 0

    def _percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return round(ordered[0], 2)
        k = (len(ordered) - 1) * percentile
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(ordered[int(k)], 2)
        return round(ordered[f] * (c - k) + ordered[c] * (k - f), 2)

    async def _stats(since: Optional[datetime] = None) -> Dict[str, Any]:
        requests = await _count("request", since)
        success = await _count("ok", since)
        success_rate = round(success / requests, 4) if requests else 0.0
        no_data = await _count("no_data", since)
        skip_disabled = await _count("skip_disabled", since)
        errors = {name: await _count(name, since) for name in ("server_error", "bad_status", "json_decode_fail", "validation_fail", "empty_content", "exception")}

        ok_details = await _details("ok", since)
        durations_ms = [
            _to_float(d.get("duration_s")) * 1000.0
            for d in ok_details
            if d.get("duration_s") is not None
        ]
        durations_ms = [v for v in durations_ms if v >= 0]
        avg_duration_ms = round(sum(durations_ms) / len(durations_ms), 2) if durations_ms else 0.0
        p95_duration_ms = _percentile(durations_ms, 0.95) if durations_ms else 0.0

        lines_proposed_total = sum(_to_int(d.get("lines")) for d in ok_details)
        avg_lines_proposed = round(lines_proposed_total / success, 2) if success else 0.0

        overall_values = [
            _to_float(d.get("overall"))
            for d in ok_details
            if d.get("overall") is not None
        ]
        avg_overall_confidence = round(sum(overall_values) / len(overall_values), 4) if overall_values else 0.0

        merged_details = await _details("merged", since)
        lines_added_total = sum(_to_int(d.get("added")) for d in merged_details)
        lines_added_avg = round(lines_added_total / success, 2) if success else 0.0
        ignored_low_total = sum(_to_int(d.get("ignored_low_conf")) for d in merged_details)
        ignored_low_avg = round(ignored_low_total / success, 2) if success else 0.0

        request_details = await _details("request", since)
        model_counts: Counter[str] = Counter()
        for d in request_details:
            model = d.get("model")
            if model:
                model_counts[str(model)] += 1
        model_usage = [
            {
                "model": model,
                "count": count,
                "share": round(count / requests, 4) if requests else 0.0,
            }
            for model, count in model_counts.most_common()
        ]

        return {
            "requests": requests,
            "success": success,
            "success_rate": success_rate,
            "no_data": no_data,
            "skip_disabled": skip_disabled,
            "errors": errors,
            "avg_overall_confidence": avg_overall_confidence,
            "lines_proposed_total": lines_proposed_total,
            "lines_proposed_avg_per_success": avg_lines_proposed,
            "lines_added_total": lines_added_total,
            "lines_added_avg_per_success": lines_added_avg,
            "ignored_low_conf_total": ignored_low_total,
            "ignored_low_conf_avg_per_success": ignored_low_avg,
            "durations_ms": {
                "count": len(durations_ms),
                "avg": avg_duration_ms,
                "p95": p95_duration_ms,
            },
            "model_usage": model_usage,
        }

    overall = await _stats()
    overall["last_24h"] = await _stats(day_ago)
    return overall


@router.post("/{name}/start", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def start(name: str, mode: Optional[str] = Query(None, description="Modo de ejecución: 'docker' o 'local' (solo para drive_sync_worker)"), db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Inicia un servicio y registra logs/uptime.
    
    Args:
        name: Nombre del servicio
        mode: Modo de ejecución ('docker' o 'local'), solo aplica a drive_sync_worker
    """
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    
    # Validar modo solo para drive_sync_worker
    if name == "drive_sync_worker" and mode and mode not in ("docker", "local"):
        raise HTTPException(status_code=400, detail="Modo debe ser 'docker' o 'local'")
    
    row = await _ensure_row(db, name)
    cid = _cid()
    t0 = time.perf_counter()
    try:
        st = _start(name, correlation_id=cid, mode=mode)
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
    """Detiene un servicio y persiste uptime acumulado."""
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
    """Detiene servicios no esenciales (best-effort)."""
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
    """Devuelve los últimos N logs del servicio."""
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
    """SSE con logs incrementales del servicio (mantiene last_id)."""
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


@router.delete("/{name}/logs", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def delete_service_logs(name: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Elimina todos los logs (ServiceLog) de un servicio.
    
    Solo se permite cuando el servicio está detenido para evitar conflictos.
    """
    if name not in KNOWN_SERVICES:
        raise HTTPException(status_code=404, detail="Servicio desconocido")
    
    # Verificar que el servicio esté detenido
    row = await _ensure_row(db, name)
    if row.status == "running":
        raise HTTPException(
            status_code=400, 
            detail="No se pueden eliminar logs mientras el servicio está corriendo. Detener el servicio primero."
        )
    
    # Eliminar todos los ServiceLog del servicio
    from sqlalchemy import delete
    cid = _cid()
    try:
        result = await db.execute(delete(ServiceLog).where(ServiceLog.service == name))
        deleted_count = result.rowcount or 0
        await db.commit()
        
        # Registrar la acción de limpieza
        db.add(ServiceLog(
            service=name,
            correlation_id=cid,
            action="delete_logs",
            host=socket.gethostname(),
            pid=None,
            duration_ms=None,
            ok=True,
            level="INFO",
            error=None,
            payload={"deleted_count": deleted_count}
        ))
        await db.commit()
        
        return {
            "name": name,
            "deleted_count": deleted_count,
            "ok": True,
            "message": f"Se eliminaron {deleted_count} logs del servicio {name}"
        }
    except Exception as e:
        await db.rollback()
        db.add(ServiceLog(
            service=name,
            correlation_id=cid,
            action="delete_logs",
            host=socket.gethostname(),
            pid=None,
            duration_ms=None,
            ok=False,
            level="ERROR",
            error=str(e),
            payload={}
        ))
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Error eliminando logs: {e}")


@router.get("/{name}/deps/check", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def deps_check(name: str) -> Dict[str, Any]:
    """Chequea dependencias de sistema/paquetes según el servicio."""
    name = name.lower()
    missing: List[str] = []
    hints: List[str] = []
    ok = True
    if name == "playwright":
        try:
            import importlib  # noqa: F401
            importlib.import_module("playwright")
        except Exception:
            ok = False
            missing.append("playwright")
            hints.append("pip install playwright && python -m playwright install chromium")
        # chromium presence is best-effort; encourage install
        hints.append("Si falta Chromium: python -m playwright install chromium")
    elif name == "pdf_import":
        # Check common external tools (with Windows fallback paths)
        tesseract = shutil.which("tesseract")
        if not tesseract:
            for p in [
                r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            ]:
                if os.path.exists(p):
                    tesseract = p
                    break
        qpdf = shutil.which("qpdf")
        gs = shutil.which("gswin64c") or shutil.which("gswin32c") or shutil.which("gs")
        if not tesseract:
            ok = False; missing.append("tesseract")
        if not qpdf:
            ok = False; missing.append("qpdf")
        if not gs:
            ok = False; missing.append("ghostscript")
        if not ok:
            hints.append("Instala Tesseract/QPDF/Ghostscript en el host/imagen")
    elif name == "image_processing":
        try:
            __import__("PIL")
        except Exception:
            ok = False; missing.append("Pillow")
        # Optional helpers
        try:
            __import__("rembg")
        except Exception:
            hints.append("pip install rembg (opcional)")
    elif name == "telegram_polling_worker":
        # Verificar que TELEGRAM_BOT_TOKEN esté configurado
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            ok = False
            missing.append("TELEGRAM_BOT_TOKEN")
            hints.append("Configurar TELEGRAM_BOT_TOKEN en .env (obtener de @BotFather)")
        # Verificar que TELEGRAM_ENABLED esté habilitado
        telegram_enabled = os.getenv("TELEGRAM_ENABLED", "0").lower() in ("1", "true", "yes")
        if not telegram_enabled:
            hints.append("Configurar TELEGRAM_ENABLED=1 en .env para habilitar")
        # Verificar dependencias Python
        try:
            import httpx
        except ImportError:
            ok = False
            missing.append("httpx")
            hints.append("pip install httpx")
    else:
        return {"ok": False, "missing": [], "detail": ["servicio desconocido"]}
    return {"ok": ok, "missing": missing, "hints": hints}


@router.post("/{name}/deps/install", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def deps_install(name: str, db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """Dev helper to install missing deps for selected services.

    Only enabled in non-production environments.
    """
    if settings.env == "production":
        return {"ok": False, "disabled": True, "hint": "Instalación deshabilitada en producción"}
    name = name.lower()
    detail: List[str] = []
    ok = True
    if name == "playwright":
        try:
            # Install chromium browser only
            proc = subprocess.run(["python", "-m", "playwright", "install", "chromium"], capture_output=True, text=True, timeout=300)
            out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            for line in out.splitlines():
                if line.strip():
                    detail.append(line.strip())
            ok = proc.returncode == 0
        except Exception as e:
            ok = False
            detail.append(str(e))
    elif name == "pdf_import":
        ok = False
        detail.append("Instalación automática de herramientas del sistema no soportada; usar gestor del sistema")
    else:
        ok = False
        detail.append("servicio desconocido")

    # Log result
    try:
        db.add(ServiceLog(service=name, correlation_id=_cid(), action="deps", host=socket.gethostname(), pid=None, duration_ms=None, ok=ok, level=("INFO" if ok else "ERROR"), error=(None if ok else "install failed"), payload={"detail": detail[:50]}))
        await db.commit()
    except Exception:
        pass
    return {"ok": ok, "detail": detail[:200]}


@router.get("/tools/health", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def tools_health() -> Dict[str, Any]:
    """Devuelve el estado de herramientas del sistema necesarias/opcionales.

    - qpdf: path, version, ok
    - ghostscript: path, version, ok (gswin64c/gswin32c/gs)
    - tesseract: path, version, ok
    - playwright: paquete instalado y navegador chromium instalado
    """
    def _which_with_windows_fallback(name: str, fallbacks: list[str] | None = None) -> Optional[str]:
        p = shutil.which(name)
        if p:
            return p
        for fp in (fallbacks or []):
            if os.path.exists(fp):
                return fp
        return None

    def _version_of(cmd: list[str]) -> Optional[str]:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            out = (proc.stdout or proc.stderr or "").strip()
            if out:
                first = out.splitlines()[0].strip()
                return first[:120]
            return None
        except Exception:
            return None

    # qpdf
    qpdf_path = _which_with_windows_fallback("qpdf")
    qpdf_ver = _version_of([qpdf_path, "--version"]) if qpdf_path else None
    qpdf_ok = bool(qpdf_path and qpdf_ver)

    # ghostscript
    gs_bin = _which_with_windows_fallback("gswin64c") or _which_with_windows_fallback("gswin32c") or _which_with_windows_fallback("gs")
    gs_ver = _version_of([gs_bin, "-v"]) if gs_bin else None
    gs_ok = bool(gs_bin and gs_ver)

    # tesseract
    tesseract_path = _which_with_windows_fallback(
        "tesseract",
        [
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
        ],
    )
    tess_ver = _version_of([tesseract_path, "--version"]) if tesseract_path else None
    tess_ok = bool(tesseract_path and tess_ver)

    # playwright
    pw_installed = False
    chromium_installed = False
    pw_version: Optional[str] = None
    try:
        import importlib
        import json as _json
        importlib.import_module("playwright")
        pw_installed = True
        # Detectar navegadores instalados: usar 'python -m playwright install --dry-run' o 'playwright --version'
        try:
            ver_proc = subprocess.run(["python", "-m", "playwright", "--version"], capture_output=True, text=True, timeout=8)
            vout = (ver_proc.stdout or ver_proc.stderr or "").strip()
            pw_version = vout.splitlines()[0][:120] if vout else None
        except Exception:
            pw_version = None
        try:
            # 'python -m playwright install --dry-run' lista los navegadores esperados; no siempre indica instalados.
            # Alternativa: intentar lanzar 'chromium --version' vía playwright show-path (no disponible estable).
            # Hacemos un smoke: 'python - <<code>>' para consultar installation via API si está disponible.
            code = (
                "from playwright.sync_api import sync_playwright;\n"
                "with sync_playwright() as p:\n"
                "    b = p.chromium\n"
                "    print('OK')\n"
            )
            probe = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=12)
            chromium_installed = (probe.returncode == 0) and ("OK" in (probe.stdout or ""))
        except Exception:
            chromium_installed = False
    except Exception:
        pw_installed = False
        chromium_installed = False

    return {
        "qpdf": {"ok": qpdf_ok, "path": qpdf_path, "version": qpdf_ver},
        "ghostscript": {"ok": gs_ok, "path": gs_bin, "version": gs_ver},
        "tesseract": {"ok": tess_ok, "path": tesseract_path, "version": tess_ver},
        "playwright": {"ok": pw_installed and chromium_installed, "package": pw_installed, "chromium": chromium_installed, "version": pw_version},
    }
    
@router.get("/notion/health", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def notion_health() -> Dict[str, Any]:
    """Health básico de Notion: flags y latencia de una consulta dummy.

    Devuelve: enabled, has_sdk, has_key, has_errors_db, dry_run, latency_ms
    """
    nw = NotionWrapper()
    cfg = load_notion_settings()
    h = nw.health()
    latency_ms = None
    if cfg.enabled and cfg.errors_db:
        import time as _t
        t0 = _t.perf_counter()
        try:
            # Fingerprint dummy que no debería existir
            _ = nw.query_by_fingerprint(cfg.errors_db, "__healthcheck__fingerprint__")
            latency_ms = int((_t.perf_counter() - t0) * 1000)
        except Exception:
            latency_ms = None
    return {**h, "latency_ms": latency_ms}


# --- Métricas: Bug Reports ---
from pathlib import Path
import json


def _date_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


@router.get("/metrics/bug-reports", dependencies=[Depends(require_roles("admin"))])
async def metrics_bug_reports(date_from: str | None = None, date_to: str | None = None, with_screenshot: int = 0) -> Dict[str, Any]:
    """Cuenta reportes por día leyendo logs/BugReport.log (JSON por línea).

    - date_from/date_to: YYYY-MM-DD (UTC base). Si faltan, se usa la ventana últimos 7 días.
    - with_screenshot=1: filtra sólo entradas que tengan `screenshot_file`.
    """
    root = Path(__file__).resolve().parents[2]
    log_path = root / "logs" / "BugReport.log"
    today = datetime.utcnow().date()
    try:
        to_d = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    except Exception:
        to_d = today
    try:
        from_d = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else (to_d - timedelta(days=6))
    except Exception:
        from_d = to_d - timedelta(days=6)

    # Preparar buckets por día
    buckets: Dict[str, int] = {}
    cur = from_d
    while cur <= to_d:
        buckets[_date_key(datetime(cur.year, cur.month, cur.day))] = 0
        cur += timedelta(days=1)

    if not log_path.exists():
        return {"days": [{"date": d, "count": c} for d, c in sorted(buckets.items())], "total": 0}

    total = 0
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                # Formato: "<ts> | LEVEL | BugReport | {json}"
                jpos = line.find("{")
                if jpos < 0:
                    continue
                try:
                    obj = json.loads(line[jpos:])
                except Exception:
                    continue
                when = obj.get("ts_gmt3") or obj.get("ts")
                if not when:
                    continue
                try:
                    dt = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
                except Exception:
                    continue
                dkey = _date_key(dt)
                if dkey < _date_key(datetime(from_d.year, from_d.month, from_d.day)) or dkey > _date_key(datetime(to_d.year, to_d.month, to_d.day)):
                    continue
                if with_screenshot and not obj.get("screenshot_file"):
                    continue
                buckets[dkey] = (buckets.get(dkey, 0) + 1)
                total += 1
    except Exception:
        # Evitar romper el panel por formatos inesperados
        pass

    return {"days": [{"date": d, "count": buckets.get(d, 0)} for d in sorted(buckets.keys())], "total": total}
