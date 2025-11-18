#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: market_scheduler.py
# NG-HEADER: Ubicación: services/routers/market_scheduler.py
# NG-HEADER: Descripción: Router para gestión del scheduler de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Router para control y monitoreo del scheduler de actualización de precios de mercado.

Endpoints:
- GET /market/scheduler/status - Estado del scheduler y estadísticas
- POST /market/scheduler/trigger - Ejecuta actualización manual
- POST /market/scheduler/enable - Habilita el scheduler
- POST /market/scheduler/disable - Deshabilita el scheduler
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth import require_role
from services.jobs.market_scheduler import (
    get_scheduler_status,
    run_manual_update,
    start_scheduler,
    stop_scheduler,
    SCHEDULER_ENABLED
)

router = APIRouter(prefix="/market/scheduler", tags=["Market Scheduler"])


# ==================== SCHEMAS ====================

class SchedulerStatusResponse(BaseModel):
    """Respuesta con estado del scheduler."""
    scheduler_enabled: bool
    cron_schedule: str
    update_frequency_days: int
    max_products_per_run: int
    prioritize_mandatory: bool
    stats: dict


class ManualTriggerRequest(BaseModel):
    """Request para ejecución manual."""
    max_products: Optional[int] = Field(
        None,
        description="Máximo de productos a procesar (override temporal)",
        gt=0,
        le=500
    )
    days_threshold: Optional[int] = Field(
        None,
        description="Días desde última actualización (override temporal)",
        gt=0,
        le=365
    )


class ManualTriggerResponse(BaseModel):
    """Respuesta de ejecución manual."""
    success: bool
    products_enqueued: int
    duration_seconds: Optional[float] = None
    message: str


class SchedulerActionResponse(BaseModel):
    """Respuesta de acciones sobre el scheduler."""
    success: bool
    message: str
    scheduler_running: bool


# ==================== ENDPOINTS ====================

@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="Obtener estado del scheduler",
    description="Retorna configuración actual y estadísticas de productos pendientes"
)
async def get_status(
    _: None = Depends(require_role(["admin", "colaborador"]))
):
    """
    Obtiene estado actual del scheduler y métricas de productos.
    
    Requiere rol: admin o colaborador
    """
    status = await get_scheduler_status()
    return status


@router.post(
    "/trigger",
    response_model=ManualTriggerResponse,
    summary="Ejecutar actualización manual",
    description="Dispara actualización inmediata sin esperar al cron"
)
async def trigger_manual_update(
    request: ManualTriggerRequest,
    _: None = Depends(require_role(["admin"]))
):
    """
    Ejecuta actualización manual de precios de mercado.
    
    Los productos se encolan en Dramatiq para procesamiento asíncrono.
    
    Requiere rol: admin
    """
    try:
        result = await run_manual_update(
            max_products=request.max_products,
            days_threshold=request.days_threshold
        )
        
        return ManualTriggerResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar actualización manual: {str(e)}"
        )


@router.post(
    "/enable",
    response_model=SchedulerActionResponse,
    summary="Habilitar scheduler",
    description="Inicia el scheduler automático de actualizaciones"
)
async def enable_scheduler(
    _: None = Depends(require_role(["admin"]))
):
    """
    Habilita e inicia el scheduler automático.
    
    Nota: Esta acción afecta solo la instancia actual. Para habilitación
    permanente, configurar MARKET_SCHEDULER_ENABLED=true en .env
    
    Requiere rol: admin
    """
    try:
        start_scheduler()
        
        return SchedulerActionResponse(
            success=True,
            message="Scheduler habilitado correctamente",
            scheduler_running=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al habilitar scheduler: {str(e)}"
        )


@router.post(
    "/disable",
    response_model=SchedulerActionResponse,
    summary="Deshabilitar scheduler",
    description="Detiene el scheduler automático de actualizaciones"
)
async def disable_scheduler(
    _: None = Depends(require_role(["admin"]))
):
    """
    Deshabilita y detiene el scheduler automático.
    
    Nota: Esta acción afecta solo la instancia actual. Las tareas ya
    encoladas en Dramatiq continuarán ejecutándose.
    
    Requiere rol: admin
    """
    try:
        stop_scheduler()
        
        return SchedulerActionResponse(
            success=True,
            message="Scheduler deshabilitado correctamente",
            scheduler_running=False
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al deshabilitar scheduler: {str(e)}"
        )
