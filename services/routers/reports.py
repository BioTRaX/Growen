#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: reports.py
# NG-HEADER: Ubicación: services/routers/reports.py
# NG-HEADER: Descripción: Endpoints de reportes (resumen ventas y export CSV)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import io, csv

from db.session import get_session
from db.models import Sale
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
