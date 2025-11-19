#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: alerts.py
# NG-HEADER: Ubicación: services/routers/alerts.py
# NG-HEADER: Descripción: Router API para gestión de alertas de precios de mercado
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Router para gestión de alertas de variación de precios de mercado.

Endpoints:
- GET /alerts - Listar alertas con filtros
- GET /alerts/stats - Estadísticas de alertas
- GET /alerts/{id} - Detalle de una alerta
- PATCH /alerts/{id}/resolve - Marcar alerta como resuelta
- POST /alerts/bulk-resolve - Resolver múltiples alertas
- DELETE /alerts/{id} - Eliminar alerta (admin only)
"""

from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketAlert, CanonicalProduct, User
from db.session import get_session
from services.auth import require_roles, current_session, SessionData
from services.market.alerts import (
    resolve_alert,
    bulk_resolve_alerts,
    get_alert_statistics,
    get_active_alerts_count
)

router = APIRouter(prefix="/alerts", tags=["Market Alerts"])


# ==================== SCHEMAS ====================

class AlertBase(BaseModel):
    """Schema base de alerta."""
    product_id: int
    alert_type: str
    severity: str
    old_value: Optional[float]
    new_value: float
    delta_percentage: float
    message: str


class AlertResponse(AlertBase):
    """Respuesta de alerta individual."""
    id: int
    resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[int]
    resolution_note: Optional[str]
    email_sent: bool
    email_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Información del producto (join)
    product_name: Optional[str] = None
    product_ng_sku: Optional[str] = None
    
    # Información del resolver (join)
    resolver_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Respuesta paginada de alertas."""
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AlertStatsResponse(BaseModel):
    """Respuesta de estadísticas."""
    active_alerts: int
    resolved_alerts: int
    critical_alerts: int
    alerts_last_24h: int
    total_alerts: int


class ResolveAlertRequest(BaseModel):
    """Request para resolver alerta."""
    resolution_note: Optional[str] = Field(None, max_length=1000)


class BulkResolveRequest(BaseModel):
    """Request para resolver múltiples alertas."""
    alert_ids: List[int] = Field(..., min_items=1, max_items=100)
    resolution_note: Optional[str] = Field(None, max_length=1000)


class BulkResolveResponse(BaseModel):
    """Respuesta de resolución en lote."""
    resolved_count: int
    message: str


# ==================== ENDPOINTS ====================

@router.get(
    "",
    response_model=AlertListResponse,
    summary="Listar alertas",
    description="Obtiene lista paginada de alertas con filtros opcionales"
)
async def list_alerts(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    resolved: Optional[bool] = Query(None, description="Filtrar por estado (true=resueltas, false=activas)"),
    severity: Optional[str] = Query(None, description="Filtrar por severidad (low, medium, high, critical)"),
    alert_type: Optional[str] = Query(None, description="Filtrar por tipo"),
    product_id: Optional[int] = Query(None, description="Filtrar por producto"),
    db: AsyncSession = Depends(get_session),
    _: None = Depends(require_roles("admin", "colaborador"))
):
    """
    Lista alertas con paginación y filtros.
    
    Requiere rol: admin o colaborador
    """
    # Query base
    query = select(MarketAlert).join(
        CanonicalProduct, MarketAlert.product_id == CanonicalProduct.id
    ).outerjoin(
        User, MarketAlert.resolved_by == User.id
    )
    
    # Aplicar filtros
    filters = []
    
    if resolved is not None:
        filters.append(MarketAlert.resolved == resolved)
    
    if severity:
        filters.append(MarketAlert.severity == severity)
    
    if alert_type:
        filters.append(MarketAlert.alert_type == alert_type)
    
    if product_id:
        filters.append(MarketAlert.product_id == product_id)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Ordenar por fecha de creación (más recientes primero)
    query = query.order_by(desc(MarketAlert.created_at))
    
    # Contar total
    count_query = select(func.count()).select_from(MarketAlert)
    if filters:
        count_query = count_query.where(and_(*filters))
    
    total = await db.scalar(count_query) or 0
    
    # Paginación
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Ejecutar query
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    # Construir respuestas
    items = []
    for alert in alerts:
        await db.refresh(alert, ["product", "resolver"])
        
        alert_data = AlertResponse(
            id=alert.id,
            product_id=alert.product_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            old_value=float(alert.old_value) if alert.old_value else None,
            new_value=float(alert.new_value),
            delta_percentage=float(alert.delta_percentage),
            message=alert.message,
            resolved=alert.resolved,
            resolved_at=alert.resolved_at,
            resolved_by=alert.resolved_by,
            resolution_note=alert.resolution_note,
            email_sent=alert.email_sent,
            email_sent_at=alert.email_sent_at,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            product_name=alert.product.name if alert.product else None,
            product_ng_sku=alert.product.ng_sku if alert.product else None,
            resolver_name=alert.resolver.email if alert.resolver else None
        )
        items.append(alert_data)
    
    # Calcular total de páginas
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return AlertListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/stats",
    response_model=AlertStatsResponse,
    summary="Estadísticas de alertas",
    description="Obtiene métricas globales de alertas"
)
async def get_stats(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(require_roles("admin", "colaborador"))
):
    """
    Obtiene estadísticas de alertas.
    
    Requiere rol: admin o colaborador
    """
    stats = await get_alert_statistics(db)
    return AlertStatsResponse(**stats)


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Detalle de alerta",
    description="Obtiene información detallada de una alerta específica"
)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(require_roles("admin", "colaborador"))
):
    """
    Obtiene detalle de una alerta.
    
    Requiere rol: admin o colaborador
    """
    query = select(MarketAlert).where(MarketAlert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    # Cargar relaciones
    await db.refresh(alert, ["product", "resolver"])
    
    return AlertResponse(
        id=alert.id,
        product_id=alert.product_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        old_value=float(alert.old_value) if alert.old_value else None,
        new_value=float(alert.new_value),
        delta_percentage=float(alert.delta_percentage),
        message=alert.message,
        resolved=alert.resolved,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
        resolution_note=alert.resolution_note,
        email_sent=alert.email_sent,
        email_sent_at=alert.email_sent_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        product_name=alert.product.name if alert.product else None,
        product_ng_sku=alert.product.ng_sku if alert.product else None,
        resolver_name=alert.resolver.email if alert.resolver else None
    )


@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolver alerta",
    description="Marca una alerta como resuelta"
)
async def resolve_alert_endpoint(
    alert_id: int,
    request: ResolveAlertRequest,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session)
):
    """
    Marca una alerta como resuelta.
    
    Requiere autenticación
    """
    alert = await resolve_alert(
        db=db,
        alert_id=alert_id,
        user_id=sess.user_id,
        resolution_note=request.resolution_note
    )
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    # Cargar relaciones
    await db.refresh(alert, ["product", "resolver"])
    
    return AlertResponse(
        id=alert.id,
        product_id=alert.product_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        old_value=float(alert.old_value) if alert.old_value else None,
        new_value=float(alert.new_value),
        delta_percentage=float(alert.delta_percentage),
        message=alert.message,
        resolved=alert.resolved,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
        resolution_note=alert.resolution_note,
        email_sent=alert.email_sent,
        email_sent_at=alert.email_sent_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        product_name=alert.product.name if alert.product else None,
        product_ng_sku=alert.product.ng_sku if alert.product else None,
        resolver_name=alert.resolver.email if alert.resolver else None
    )


@router.post(
    "/bulk-resolve",
    response_model=BulkResolveResponse,
    summary="Resolver múltiples alertas",
    description="Marca varias alertas como resueltas en lote"
)
async def bulk_resolve_endpoint(
    request: BulkResolveRequest,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session)
):
    """
    Resuelve múltiples alertas en lote.
    
    Requiere autenticación
    """
    count = await bulk_resolve_alerts(
        db=db,
        alert_ids=request.alert_ids,
        user_id=sess.user_id,
        resolution_note=request.resolution_note
    )
    
    return BulkResolveResponse(
        resolved_count=count,
        message=f"{count} alerta(s) resuelta(s) exitosamente"
    )


@router.delete(
    "/{alert_id}",
    summary="Eliminar alerta",
    description="Elimina permanentemente una alerta (admin only)"
)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(require_roles("admin"))
):
    """
    Elimina una alerta permanentemente.
    
    Requiere rol: admin
    """
    query = select(MarketAlert).where(MarketAlert.id == alert_id)
    result = await db.execute(query)
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    await db.delete(alert)
    await db.commit()
    
    return {"message": "Alerta eliminada exitosamente"}
