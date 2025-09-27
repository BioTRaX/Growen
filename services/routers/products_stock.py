#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: products_stock.py
# NG-HEADER: Ubicación: services/routers/products_stock.py
# NG-HEADER: Descripción: Endpoints de historial de stock (stock_ledger) por producto.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from services.auth import require_roles
from db.session import get_session
from db.models import Product, StockLedger

router = APIRouter(prefix="/products", tags=["stock"])

"""Se utiliza el modelo ORM StockLedger (evitamos definición Table duplicada)."""

@router.get("/{product_id}/stock/history", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def product_stock_history(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Historial de movimientos de stock para un producto.

    Fuente: tabla stock_ledger.
    Orden: descendente por created_at (fallback por id). Paginado simple.
    """
    prod = await db.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    # Total (conteo rápido)
    from sqlalchemy import func
    total = await db.scalar(select(func.count()).select_from(select(StockLedger.id).where(StockLedger.product_id == product_id).subquery()))
    q = (
        select(StockLedger)
        .where(StockLedger.product_id == product_id)
        .order_by(desc(StockLedger.created_at), desc(StockLedger.id))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(q)).scalars().all()
    items = [{
        "id": r.id,
        "at": (r.created_at.isoformat() if getattr(r, 'created_at', None) else None),
        "delta": r.delta,
        "balance_after": r.balance_after,
        "source_type": r.source_type,
        "source_id": r.source_id,
        "meta": r.meta or {},
    } for r in rows]
    pages = ((int(total or 0) + page_size - 1) // page_size) if total else 0
    return {"product_id": product_id, "items": items, "total": int(total or 0), "page": page, "pages": pages}
