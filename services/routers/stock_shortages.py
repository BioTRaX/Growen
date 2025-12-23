# NG-HEADER: Nombre de archivo: stock_shortages.py
# NG-HEADER: Ubicación: services/routers/stock_shortages.py
# NG-HEADER: Descripción: Endpoints para gestión de faltantes de stock (shortages)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Endpoints para faltantes de stock (shortages).

Proporciona CRUD y estadísticas para reportar y gestionar mermas,
regalos y ventas pendientes que afectan el inventario.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, StockShortage, StockLedger, User
from db.session import get_session
from services.auth import require_roles, current_session, SessionData

router = APIRouter(tags=["stock_shortages"])


# --- Pydantic Schemas ---

class CreateShortageRequest(BaseModel):
    """Payload para crear un nuevo reporte de faltante."""
    product_id: int = Field(..., description="ID del producto afectado")
    quantity: int = Field(..., gt=0, description="Cantidad a descontar (siempre positivo)")
    reason: str = Field(..., pattern="^(GIFT|PENDING_SALE|UNKNOWN)$", description="Motivo del faltante")
    observation: Optional[str] = Field(None, max_length=1000, description="Observación opcional")


class ShortageResponse(BaseModel):
    """Respuesta de un faltante."""
    id: int
    product_id: int
    product_title: str
    quantity: int
    reason: str
    status: str
    observation: Optional[str]
    user_name: Optional[str]
    created_at: str


class ShortageStatsResponse(BaseModel):
    """Estadísticas de faltantes."""
    total_items: int
    total_quantity: int
    by_reason: dict[str, int]
    this_month: int


# --- Endpoints ---

@router.post("/shortages", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def create_shortage(
    payload: CreateShortageRequest,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    request: Request = None,
):
    """
    Crea un reporte de faltante y descuenta stock de forma atómica.
    
    El stock del producto se reduce inmediatamente. Se permite stock negativo
    pero se devuelve un warning en la respuesta.
    """
    # Validar producto existe
    product = await db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Calcular nuevo stock (puede ser negativo)
    old_stock = product.stock or 0
    new_stock = old_stock - payload.quantity
    
    # Crear registro de faltante
    shortage = StockShortage(
        product_id=payload.product_id,
        user_id=sess.user_id if sess else None,
        quantity=payload.quantity,
        reason=payload.reason,
        status="OPEN",
        observation=payload.observation,
    )
    db.add(shortage)
    await db.flush()  # Para obtener el ID
    
    # Actualizar stock del producto
    product.stock = new_stock
    
    # Registrar en ledger para trazabilidad
    ledger = StockLedger(
        product_id=payload.product_id,
        source_type="shortage",
        source_id=shortage.id,
        delta=-payload.quantity,
        balance_after=new_stock,
        meta={"reason": payload.reason, "observation": payload.observation or ""},
    )
    db.add(ledger)
    
    await db.commit()
    
    # Respuesta con warning si stock negativo
    result = {
        "id": shortage.id,
        "product_id": payload.product_id,
        "product_title": product.title,
        "quantity": payload.quantity,
        "reason": payload.reason,
        "new_stock": new_stock,
    }
    
    if new_stock < 0:
        result["warning"] = f"El stock resultante es negativo ({new_stock})"
    
    return result


@router.get("/shortages", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_shortages(
    reason: Optional[str] = Query(None, description="Filtrar por motivo (GIFT/PENDING_SALE/UNKNOWN)"),
    status: Optional[str] = Query(None, description="Filtrar por estado (OPEN/RECONCILED)"),
    product_id: Optional[int] = Query(None, description="Filtrar por producto"),
    date_from: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """
    Listado paginado de faltantes con filtros opcionales.
    """
    # Base query
    q = select(StockShortage).order_by(desc(StockShortage.created_at))
    count_q = select(func.count()).select_from(StockShortage)
    
    # Aplicar filtros
    if reason:
        q = q.where(StockShortage.reason == reason)
        count_q = count_q.where(StockShortage.reason == reason)
    if status:
        q = q.where(StockShortage.status == status)
        count_q = count_q.where(StockShortage.status == status)
    if product_id:
        q = q.where(StockShortage.product_id == product_id)
        count_q = count_q.where(StockShortage.product_id == product_id)
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.where(StockShortage.created_at >= dt_from)
            count_q = count_q.where(StockShortage.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            q = q.where(StockShortage.created_at < dt_to)
            count_q = count_q.where(StockShortage.created_at < dt_to)
        except ValueError:
            pass
    
    # Conteo total
    total = await db.scalar(count_q) or 0
    
    # Paginación
    q = q.limit(page_size).offset((page - 1) * page_size)
    
    rows = (await db.execute(q)).scalars().all()
    
    # Obtener productos y usuarios para enriquecer respuesta
    product_ids = list(set(r.product_id for r in rows))
    user_ids = list(set(r.user_id for r in rows if r.user_id))
    
    products = {}
    if product_ids:
        prods = (await db.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()
        products = {p.id: p.title for p in prods}
    
    users = {}
    if user_ids:
        usrs = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u.name for u in usrs}
    
    items = [
        {
            "id": r.id,
            "product_id": r.product_id,
            "product_title": products.get(r.product_id, ""),
            "quantity": r.quantity,
            "reason": r.reason,
            "status": r.status,
            "observation": r.observation,
            "user_name": users.get(r.user_id) if r.user_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    
    pages = ((total + page_size - 1) // page_size) if total else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/shortages/stats", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def shortages_stats(
    db: AsyncSession = Depends(get_session),
):
    """
    Estadísticas simples de faltantes para el dashboard.
    """
    # Total items y cantidad
    total_items = await db.scalar(select(func.count()).select_from(StockShortage)) or 0
    total_quantity = await db.scalar(select(func.coalesce(func.sum(StockShortage.quantity), 0))) or 0
    
    # Por motivo
    by_reason_query = (
        select(StockShortage.reason, func.count())
        .group_by(StockShortage.reason)
    )
    by_reason_result = (await db.execute(by_reason_query)).all()
    by_reason = {r[0]: r[1] for r in by_reason_result}
    
    # Este mes
    first_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = await db.scalar(
        select(func.count())
        .select_from(StockShortage)
        .where(StockShortage.created_at >= first_of_month)
    ) or 0
    
    return {
        "total_items": total_items,
        "total_quantity": int(total_quantity),
        "by_reason": by_reason,
        "this_month": this_month,
    }
