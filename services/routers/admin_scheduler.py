#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: admin_scheduler.py
# NG-HEADER: Ubicación: services/routers/admin_scheduler.py
# NG-HEADER: Descripción: Endpoints de administración del scheduler de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Router para administración del scheduler de actualización de precios de mercado.

Endpoints:
- GET /admin/scheduler/status - Estado del scheduler
- POST /admin/scheduler/start - Iniciar scheduler
- POST /admin/scheduler/stop - Detener scheduler
- POST /admin/scheduler/run-now - Ejecutar actualización inmediata
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SchedulerRun, SchedulerSetting
from db.session import get_session
from services.auth import require_csrf, require_roles, SessionData
from services.jobs.market_scheduler import (
    get_scheduler_status,
    start_scheduler,
    stop_scheduler,
    run_manual_update,
    update_scheduler_config,
    get_is_working,
)
from services.jobs import market_scheduler as market_scheduler_job

router = APIRouter(prefix="/admin/scheduler", tags=["Admin - Scheduler"])


# ==================== SCHEMAS ====================

class SchedulerStatusResponse(BaseModel):
    """Respuesta con estado del scheduler"""
    
    running: bool = Field(description="Si el scheduler está en ejecución")
    enabled: bool = Field(description="Si está habilitado por configuración")
    working: bool = Field(description="Si está ejecutando una tarea ahora mismo")
    cron_schedule: str = Field(description="Expresión cron de la programación")
    start_hour: str = Field(description="Hora de inicio (HH:MM en GMT-3)")
    timezone: str = Field(description="Zona horaria IANA")
    interval_hours: int = Field(description="Intervalo entre ejecuciones (horas)")
    next_run_time: Optional[str] = Field(None, description="Próxima ejecución programada (ISO)")
    update_frequency_days: int = Field(description="Frecuencia de actualización en días")
    max_products_per_run: int = Field(description="Máximo de productos por ejecución")
    prioritize_mandatory: bool = Field(description="Si prioriza fuentes obligatorias")
    stats: dict = Field(description="Estadísticas de productos")


class RunManualRequest(BaseModel):
    """Request para ejecución manual"""
    
    max_products: Optional[int] = Field(None, ge=1, le=500, description="Límite de productos (1-500)")
    days_threshold: Optional[int] = Field(None, ge=0, le=365, description="Días desde última actualización (0-365)")


class RunManualResponse(BaseModel):
    """Respuesta de ejecución manual"""
    
    success: bool
    message: str
    products_enqueued: int
    sources_total: int
    duration_seconds: float
    run_id: str


def _user_id(session: SessionData) -> int | None:
    if session.user:
        return session.user.id
    value = getattr(session, "user_id", None)
    return int(value) if value is not None else None


async def _settings(db: AsyncSession) -> SchedulerSetting:
    setting = await db.get(SchedulerSetting, 1)
    if setting:
        return setting
    setting = SchedulerSetting(
        id=1,
        enabled=os.getenv("MARKET_SCHEDULER_ENABLED", "false").lower() == "true",
        start_hour=os.getenv("MARKET_SCHEDULER_START_HOUR", "02:00"),
        interval_hours=int(os.getenv("MARKET_SCHEDULER_INTERVAL_HOURS", "24")),
        update_frequency_days=int(os.getenv("MARKET_UPDATE_FREQUENCY_DAYS", "2")),
        max_products_per_run=int(os.getenv("MARKET_MAX_PRODUCTS_PER_RUN", "50")),
        prioritize_mandatory=os.getenv("MARKET_PRIORITIZE_MANDATORY", "true").lower() == "true",
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


# ==================== ENDPOINTS ====================

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_status(
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Obtiene el estado actual del scheduler y estadísticas de productos.
    
    **Requiere rol**: admin
    """
    # Obtener estadísticas del scheduler
    status_data = await get_scheduler_status()
    setting = await _settings(db)
    
    # Verificar si scheduler está corriendo
    running = False
    next_run = None
    
    scheduler = market_scheduler_job.scheduler
    if scheduler is not None and scheduler.running:
        running = True
        job = scheduler.get_job("market_price_update")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    
    return SchedulerStatusResponse(
        running=running,
        enabled=setting.enabled,
        working=status_data.get("is_working", False),
        cron_schedule=status_data["cron_schedule"],
        start_hour=setting.start_hour,
        timezone=setting.timezone,
        interval_hours=setting.interval_hours,
        next_run_time=next_run,
        update_frequency_days=setting.update_frequency_days,
        max_products_per_run=setting.max_products_per_run,
        prioritize_mandatory=setting.prioritize_mandatory,
        stats=status_data["stats"],
    )


@router.post("/start", dependencies=[Depends(require_csrf)])
async def start(
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Inicia el scheduler automático de actualización de precios.
    
    **Requiere rol**: admin
    
    **Nota**: El scheduler debe estar habilitado en la configuración 
    (MARKET_SCHEDULER_ENABLED=true) para poder iniciarse.
    """
    try:
        setting = await _settings(db)
        setting.enabled = True
        setting.updated_by_user_id = _user_id(session_data)
        setting.updated_at = datetime.utcnow()
        await db.commit()
        start_scheduler(setting.start_hour, setting.interval_hours, force=True)
        
        # Obtener info del próximo run
        next_run = None
        scheduler = market_scheduler_job.scheduler
        if scheduler and scheduler.running:
            job = scheduler.get_job("market_price_update")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return {
            "success": True,
            "message": "Scheduler iniciado correctamente",
            "next_run_time": next_run,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al iniciar scheduler: {str(e)}"
        )


@router.post("/stop", dependencies=[Depends(require_csrf)])
async def stop(
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Detiene el scheduler automático de actualización de precios.
    
    **Requiere rol**: admin
    
    **Nota**: Las tareas ya encoladas en Dramatiq continuarán ejecutándose.
    Solo se detendrá la programación de nuevas ejecuciones.
    """
    try:
        stop_scheduler()
        setting = await _settings(db)
        setting.enabled = False
        setting.updated_by_user_id = _user_id(session_data)
        setting.updated_at = datetime.utcnow()
        await db.commit()
        
        return {
            "success": True,
            "message": "Scheduler detenido correctamente",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al detener scheduler: {str(e)}"
        )


@router.post("/run-now", response_model=RunManualResponse, dependencies=[Depends(require_csrf)])
async def run_now(
    request: RunManualRequest = RunManualRequest(),
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Ejecuta una actualización manual de precios de inmediato.
    
    **Requiere rol**: admin
    
    No espera al scheduler, ejecuta una tanda de actualización de forma inmediata
    con los parámetros especificados (o los valores por defecto de configuración).
    
    Las tareas se encolan en Dramatiq para procesamiento asíncrono.
    """
    try:
        setting = await _settings(db)
        run_id = uuid.uuid4().hex
        run = SchedulerRun(
            id=run_id,
            trigger="manual",
            status="running",
            initiated_by_user_id=_user_id(session_data),
            started_at=datetime.utcnow(),
            config_snapshot={
                "max_products": request.max_products or setting.max_products_per_run,
                "days_threshold": request.days_threshold if request.days_threshold is not None else setting.update_frequency_days,
            },
        )
        db.add(run)
        await db.commit()
        result = await run_manual_update(
            max_products=request.max_products or setting.max_products_per_run,
            days_threshold=request.days_threshold if request.days_threshold is not None else setting.update_frequency_days,
        )
        run.status = "completed"
        run.products_enqueued = result["products_enqueued"]
        run.sources_total = result.get("sources_total", 0)
        run.duration_seconds = result.get("duration_seconds", 0.0)
        run.completed_at = datetime.utcnow()
        await db.commit()
        
        return RunManualResponse(
            success=True,
            message=result.get("message", f"Actualización manual iniciada: {result['products_enqueued']} productos encolados"),
            products_enqueued=result["products_enqueued"],
            sources_total=result.get("sources_total", 0),
            duration_seconds=result.get("duration_seconds", 0.0),
            run_id=run_id,
        )
    except Exception as e:
        if "run" in locals():
            run.status = "failed"
            run.error_message = str(e)[:2000]
            run.completed_at = datetime.utcnow()
            await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar actualización manual: {str(e)}"
        )


class SchedulerConfigRequest(BaseModel):
    """Request para actualizar configuración del scheduler"""
    
    start_hour: str = Field(description="Hora de inicio en formato HH:MM (GMT-3, Argentina)", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    interval_hours: int = Field(description="Intervalo entre ejecuciones en horas", ge=1, le=24)
    timezone: str = Field(default="America/Argentina/Buenos_Aires", min_length=3, max_length=64)
    update_frequency_days: int = Field(default=2, ge=0, le=365)
    max_products_per_run: int = Field(default=50, ge=1, le=500)
    prioritize_mandatory: bool = True


class SchedulerConfigResponse(BaseModel):
    """Respuesta de actualización de configuración"""
    
    success: bool
    message: str
    start_hour: str
    interval_hours: int
    timezone: str
    update_frequency_days: int
    max_products_per_run: int
    prioritize_mandatory: bool
    next_run_time: Optional[str] = None


@router.post("/config", response_model=SchedulerConfigResponse, dependencies=[Depends(require_csrf)])
async def update_config(
    request: SchedulerConfigRequest,
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza la configuración del scheduler (hora de inicio e intervalo).
    
    **Requiere rol**: admin
    
    Si el scheduler está corriendo, lo reinicia con la nueva configuración.
    La hora debe estar en formato HH:MM y se interpreta como GMT-3 (Argentina).
    """
    try:
        update_scheduler_config(request.start_hour, request.interval_hours)
        setting = await _settings(db)
        setting.start_hour = request.start_hour
        setting.interval_hours = request.interval_hours
        setting.timezone = request.timezone
        setting.update_frequency_days = request.update_frequency_days
        setting.max_products_per_run = request.max_products_per_run
        setting.prioritize_mandatory = request.prioritize_mandatory
        setting.updated_by_user_id = _user_id(session_data)
        setting.updated_at = datetime.utcnow()
        await db.commit()
        
        # Obtener próxima ejecución si está corriendo
        next_run = None
        scheduler = market_scheduler_job.scheduler
        if scheduler and scheduler.running:
            job = scheduler.get_job("market_price_update")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return SchedulerConfigResponse(
            success=True,
            message=f"Configuración actualizada: inicio {request.start_hour} GMT-3, intervalo {request.interval_hours}h",
            start_hour=request.start_hour,
            interval_hours=request.interval_hours,
            timezone=request.timezone,
            update_frequency_days=request.update_frequency_days,
            max_products_per_run=request.max_products_per_run,
            prioritize_mandatory=request.prioritize_mandatory,
            next_run_time=next_run,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar configuración: {str(e)}"
        )


@router.post("/toggle", dependencies=[Depends(require_csrf)])
async def toggle(
    session_data: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
):
    """
    Alterna el estado del scheduler (inicia si está detenido, detiene si está corriendo).
    
    **Requiere rol**: admin
    """
    try:
        scheduler = market_scheduler_job.scheduler
        if scheduler is not None and scheduler.running:
            stop_scheduler()
            setting = await _settings(db)
            setting.enabled = False
            setting.updated_by_user_id = _user_id(session_data)
            await db.commit()
            return {
                "success": True,
                "message": "Scheduler detenido",
                "running": False,
            }
        else:
            setting = await _settings(db)
            setting.enabled = True
            setting.updated_by_user_id = _user_id(session_data)
            await db.commit()
            start_scheduler(setting.start_hour, setting.interval_hours, force=True)
            scheduler = market_scheduler_job.scheduler
            next_run = None
            if scheduler and scheduler.running:
                job = scheduler.get_job("market_price_update")
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()
            return {
                "success": True,
                "message": "Scheduler iniciado",
                "running": True,
                "next_run_time": next_run,
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al alternar scheduler: {str(e)}"
        )


@router.get("/runs")
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _session: SessionData = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    total = await db.scalar(select(func.count()).select_from(SchedulerRun)) or 0
    runs = await db.scalars(
        select(SchedulerRun)
        .order_by(desc(SchedulerRun.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [
            {
                "id": run.id,
                "trigger": run.trigger,
                "status": run.status,
                "products_enqueued": run.products_enqueued,
                "sources_total": run.sources_total,
                "duration_seconds": float(run.duration_seconds) if run.duration_seconds is not None else None,
                "error_message": run.error_message,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
