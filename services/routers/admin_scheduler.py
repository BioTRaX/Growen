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

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import require_roles, SessionData
from services.jobs.market_scheduler import (
    get_scheduler_status,
    start_scheduler,
    stop_scheduler,
    run_manual_update,
    update_scheduler_config,
    get_is_working,
    scheduler,
)

router = APIRouter(prefix="/admin/scheduler", tags=["Admin - Scheduler"])


# ==================== SCHEMAS ====================

class SchedulerStatusResponse(BaseModel):
    """Respuesta con estado del scheduler"""
    
    running: bool = Field(description="Si el scheduler está en ejecución")
    enabled: bool = Field(description="Si está habilitado por configuración")
    working: bool = Field(description="Si está ejecutando una tarea ahora mismo")
    cron_schedule: str = Field(description="Expresión cron de la programación")
    start_hour: str = Field(description="Hora de inicio (HH:MM en GMT-3)")
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


# ==================== ENDPOINTS ====================

@router.get("/status", response_model=SchedulerStatusResponse)
async def get_status(
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Obtiene el estado actual del scheduler y estadísticas de productos.
    
    **Requiere rol**: admin
    """
    # Obtener estadísticas del scheduler
    status_data = await get_scheduler_status()
    
    # Verificar si scheduler está corriendo
    running = False
    next_run = None
    
    if scheduler is not None and scheduler.running:
        running = True
        job = scheduler.get_job("market_price_update")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    
    return SchedulerStatusResponse(
        running=running,
        enabled=status_data["scheduler_enabled"],
        working=status_data.get("is_working", False),
        cron_schedule=status_data["cron_schedule"],
        start_hour=status_data.get("start_hour", "02:00"),
        interval_hours=status_data.get("interval_hours", 24),
        next_run_time=next_run,
        update_frequency_days=status_data["update_frequency_days"],
        max_products_per_run=status_data["max_products_per_run"],
        prioritize_mandatory=status_data["prioritize_mandatory"],
        stats=status_data["stats"],
    )


@router.post("/start")
async def start(
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Inicia el scheduler automático de actualización de precios.
    
    **Requiere rol**: admin
    
    **Nota**: El scheduler debe estar habilitado en la configuración 
    (MARKET_SCHEDULER_ENABLED=true) para poder iniciarse.
    """
    try:
        start_scheduler()
        
        # Obtener info del próximo run
        next_run = None
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


@router.post("/stop")
async def stop(
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Detiene el scheduler automático de actualización de precios.
    
    **Requiere rol**: admin
    
    **Nota**: Las tareas ya encoladas en Dramatiq continuarán ejecutándose.
    Solo se detendrá la programación de nuevas ejecuciones.
    """
    try:
        stop_scheduler()
        
        return {
            "success": True,
            "message": "Scheduler detenido correctamente",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al detener scheduler: {str(e)}"
        )


@router.post("/run-now", response_model=RunManualResponse)
async def run_now(
    request: RunManualRequest = RunManualRequest(),
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Ejecuta una actualización manual de precios de inmediato.
    
    **Requiere rol**: admin
    
    No espera al scheduler, ejecuta una tanda de actualización de forma inmediata
    con los parámetros especificados (o los valores por defecto de configuración).
    
    Las tareas se encolan en Dramatiq para procesamiento asíncrono.
    """
    try:
        result = await run_manual_update(
            max_products=request.max_products,
            days_threshold=request.days_threshold,
        )
        
        return RunManualResponse(
            success=True,
            message=result.get("message", f"Actualización manual iniciada: {result['products_enqueued']} productos encolados"),
            products_enqueued=result["products_enqueued"],
            sources_total=result.get("sources_total", 0),
            duration_seconds=result.get("duration_seconds", 0.0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar actualización manual: {str(e)}"
        )


class SchedulerConfigRequest(BaseModel):
    """Request para actualizar configuración del scheduler"""
    
    start_hour: str = Field(description="Hora de inicio en formato HH:MM (GMT-3, Argentina)", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    interval_hours: int = Field(description="Intervalo entre ejecuciones en horas", ge=1, le=24)


class SchedulerConfigResponse(BaseModel):
    """Respuesta de actualización de configuración"""
    
    success: bool
    message: str
    start_hour: str
    interval_hours: int
    next_run_time: Optional[str] = None


@router.post("/config", response_model=SchedulerConfigResponse)
async def update_config(
    request: SchedulerConfigRequest,
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Actualiza la configuración del scheduler (hora de inicio e intervalo).
    
    **Requiere rol**: admin
    
    Si el scheduler está corriendo, lo reinicia con la nueva configuración.
    La hora debe estar en formato HH:MM y se interpreta como GMT-3 (Argentina).
    """
    try:
        update_scheduler_config(request.start_hour, request.interval_hours)
        
        # Obtener próxima ejecución si está corriendo
        next_run = None
        if scheduler and scheduler.running:
            job = scheduler.get_job("market_price_update")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return SchedulerConfigResponse(
            success=True,
            message=f"Configuración actualizada: inicio {request.start_hour} GMT-3, intervalo {request.interval_hours}h",
            start_hour=request.start_hour,
            interval_hours=request.interval_hours,
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


@router.post("/toggle")
async def toggle(
    _session: SessionData = Depends(require_roles(["admin"]))
):
    """
    Alterna el estado del scheduler (inicia si está detenido, detiene si está corriendo).
    
    **Requiere rol**: admin
    """
    try:
        if scheduler is not None and scheduler.running:
            stop_scheduler()
            return {
                "success": True,
                "message": "Scheduler detenido",
                "running": False,
            }
        else:
            start_scheduler()
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
