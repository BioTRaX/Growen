#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: reports.py
# NG-HEADER: Ubicación: services/routers/reports.py
# NG-HEADER: Descripción: Endpoints de reportes (resumen ventas y export CSV)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import io, csv

from db.session import get_session
from db.models import Sale, SalePayment
from services.auth import require_roles

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_summary(dt_from: str | None = Query(None), dt_to: str | None = Query(None), db: AsyncSession = Depends(get_session)):
    stmt = select(Sale.status, func.count(Sale.id), func.coalesce(func.sum(Sale.total_amount), 0)).group_by(Sale.status)
    if dt_from:
        try:
            d = datetime.fromisoformat(dt_from.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date >= d)
        except Exception:
            pass
    if dt_to:
        try:
            d = datetime.fromisoformat(dt_to.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date <= d)
        except Exception:
            pass
    rows = (await db.execute(stmt)).all()
    total_sales = 0
    total_amount = 0.0
    breakdown = []
    for status, count, amt in rows:
        total_sales += int(count or 0)
        total_amount += float(amt or 0)
        breakdown.append({"status": status, "count": int(count or 0), "amount": float(amt or 0)})
    return {"total_sales": total_sales, "total_amount": round(total_amount,2), "breakdown": breakdown}


@router.get("/sales/payments", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_payments_report(
    from_date: str | None = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    method: str | None = Query(None, description="Método de pago a filtrar"),
    limit: int = Query(500, ge=1, le=5000, description="Máximo de pagos devueltos"),
    db: AsyncSession = Depends(get_session),
):
    """Reporte de cobranzas (pagos de ventas) con filtros simples.

    Filtros:
      - from_date / to_date: se aplican sobre SalePayment.created_at (UTC). Formato YYYY-MM-DD.
      - method: filtra por método exacto.

    Respuesta:
      - count: cantidad de pagos devueltos (post-limit)
      - total_amount: suma de amount
      - by_method: dict método -> suma
      - items: lista de pagos (id, sale_id, method, amount, reference, created_at)
      - filters: eco de filtros aplicados
    """
    # Build query
    stmt = select(SalePayment)
    from_dt = None
    to_dt = None
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        except Exception:
            raise HTTPException(status_code=400, detail="from_date formato inválido (YYYY-MM-DD)")
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            # incluir día completo: usamos < to_dt+1
            to_dt = to_dt + timedelta(days=1)
        except Exception:
            raise HTTPException(status_code=400, detail="to_date formato inválido (YYYY-MM-DD)")
    if from_dt:
        stmt = stmt.where(SalePayment.created_at >= from_dt)
    if to_dt:
        stmt = stmt.where(SalePayment.created_at < to_dt)
    if method:
        stmt = stmt.where(SalePayment.method == method)
    stmt = stmt.order_by(SalePayment.created_at.asc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    total_amount = 0.0
    by_method: dict[str, float] = {}
    items = []
    for r in rows:
        amt = float(r.amount or 0)
        total_amount += amt
        m = r.method or "-"
        by_method[m] = by_method.get(m, 0.0) + amt
        items.append({
            "id": r.id,
            "sale_id": r.sale_id,
            "method": r.method,
            "amount": amt,
            "reference": r.reference,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {
        "count": len(items),
        "total_amount": round(total_amount, 2),
        "by_method": by_method,
        "items": items,
        "filters": {"from_date": from_date, "to_date": to_date, "method": method}
    }


@router.get("/sales/export.csv", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_export_csv(dt_from: str | None = Query(None), dt_to: str | None = Query(None), db: AsyncSession = Depends(get_session)):
    stmt = select(Sale.id, Sale.sale_date, Sale.status, Sale.customer_id, Sale.total_amount, Sale.paid_total).order_by(Sale.id.asc())
    if dt_from:
        try:
            d = datetime.fromisoformat(dt_from.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date >= d)
        except Exception:
            pass
    if dt_to:
        try:
            d = datetime.fromisoformat(dt_to.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date <= d)
        except Exception:
            pass
    rows = (await db.execute(stmt)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["sale_id","sale_date","status","customer_id","total","paid_total"])
    for rid, sdate, status, cid, total, paid in rows:
        writer.writerow([rid, sdate.isoformat(), status, cid or '', float(total or 0), float(paid or 0)])
    data = buf.getvalue().encode("utf-8")
    headers = {"Content-Disposition": "attachment; filename=sales_export.csv"}
    return Response(content=data, media_type="text/csv", headers=headers)
