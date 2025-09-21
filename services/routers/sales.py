# NG-HEADER: Nombre de archivo: sales.py
# NG-HEADER: Ubicación: services/routers/sales.py
# NG-HEADER: Descripción: Endpoints de clientes y ventas (CRUD clientes, registrar venta, adjuntos)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_session
from db.models import Customer, Sale, SaleLine, SalePayment, SaleAttachment, Product, AuditLog
from services.auth import require_roles, require_csrf, current_session, SessionData
from services.media import save_upload, get_media_root

router = APIRouter(prefix="/sales", tags=["sales"])


# --- Clientes ---
@router.get("/customers", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_customers(q: Optional[str] = None, page: int = 1, page_size: int = 50, db: AsyncSession = Depends(get_session)):
    stmt = select(Customer)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(Customer.name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like), Customer.doc_id.ilike(like))
        )
    total = (await db.execute(stmt)).scalars().all()
    items = total[(page-1)*page_size: page*page_size]
    return {
        "items": [
            {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "doc_id": c.doc_id}
            for c in items
        ],
        "total": len(total),
        "page": page,
        "pages": (len(total) + page_size - 1)//page_size,
    }


@router.post("/customers", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_customer(payload: dict, db: AsyncSession = Depends(get_session)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name es obligatorio")
    c = Customer(
        name=name,
        email=(payload.get("email") or None),
        phone=(payload.get("phone") or None),
        doc_id=(payload.get("doc_id") or None),
        address=(payload.get("address") or None),
        notes=(payload.get("notes") or None),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return {"id": c.id}


@router.put("/customers/{cid}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def update_customer(cid: int, payload: dict, db: AsyncSession = Depends(get_session)):
    c = await db.get(Customer, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for f in ("name","email","phone","doc_id","address","notes"):
        if f in payload:
            setattr(c, f, payload.get(f))
    await db.commit()
    return {"status": "ok"}


# --- Ventas ---


@router.post("", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_sale(payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    """Crea una venta y descuenta stock inmediatamente.

    payload esperado:
    - customer: { id?: number, name?: string, email?, phone?, doc_id? } (si no existe y no se pasa id, se crea con mínimos)
    - items: [ { product_id: number, qty: number, unit_price?: number, line_discount?: number } ]
    - payments?: [ { method: string, amount: number, reference?: string } ]
    - note?: string
    - status?: 'BORRADOR' | 'CONFIRMADA' (default CONFIRMADA)
    - sale_date?: ISO datetime
    - attachments?: [{ filename, content? (no soportado aquí) }]
    """
    customer_payload = payload.get("customer") or {}
    items = payload.get("items") or []
    payments = payload.get("payments") or []
    status = payload.get("status") or "CONFIRMADA"
    note = payload.get("note") or None

    if not items:
        raise HTTPException(status_code=400, detail="Debe enviar items")

    # Cliente existente o crear mínimo
    customer_id: Optional[int] = customer_payload.get("id") if isinstance(customer_payload, dict) else None
    customer_obj: Optional[Customer] = None
    if customer_id:
        customer_obj = await db.get(Customer, int(customer_id))
        if not customer_obj:
            raise HTTPException(status_code=400, detail="Cliente no existe")
    else:
        name = (customer_payload.get("name") or "Consumidor Final").strip() or "Consumidor Final"
        customer_obj = Customer(
            name=name,
            email=(customer_payload.get("email") or None),
            phone=(customer_payload.get("phone") or None),
            doc_id=(customer_payload.get("doc_id") or None),
        )
        db.add(customer_obj)
        await db.flush()

    sale = Sale(
        customer_id=customer_obj.id if customer_obj else None,
        status=status,
        sale_date=datetime.fromisoformat(payload.get("sale_date")) if payload.get("sale_date") else datetime.utcnow(),
        note=note,
        created_by=sess.user_id if getattr(sess, "user_id", None) else None,
        total_amount=Decimal("0"),
    )
    db.add(sale)
    await db.flush()

    # Crear líneas y descontar stock
    total = Decimal("0")
    for it in items:
        pid = int(it.get("product_id"))
        qty = Decimal(str(it.get("qty")))
        if qty <= 0:
            raise HTTPException(status_code=400, detail="qty debe ser > 0")
        prod = await db.get(Product, pid)
        if not prod:
            raise HTTPException(status_code=400, detail=f"Producto {pid} no encontrado")
        current_stock = int(prod.stock or 0)
        if current_stock < int(qty):
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para producto {pid}")
        unit_price = Decimal(str(it.get("unit_price") or 0)) or Decimal(str(prod.variants[0].price if prod.variants else 0))
        line_discount = Decimal(str(it.get("line_discount") or 0))
        line_total = (unit_price * qty) * (Decimal("1") - (line_discount/Decimal("100")))

        sl = SaleLine(
            sale_id=sale.id,
            product_id=pid,
            qty=qty,
            unit_price=unit_price,
            line_discount=line_discount,
        )
        db.add(sl)
        # Descontar stock
        prod.stock = current_stock - int(qty)
        total += line_total

    # Pagos (opcional)
    paid_total = Decimal("0")
    for p in payments:
        sp = SalePayment(
            sale_id=sale.id,
            method=str(p.get("method") or "efectivo"),
            amount=Decimal(str(p.get("amount") or 0)),
            reference=(p.get("reference") or None),
        )
        db.add(sp)
        paid_total += Decimal(str(p.get("amount") or 0))

    sale.total_amount = total
    sale.paid_total = paid_total

    # AuditLog
    db.add(AuditLog(action="sale_create", table="sales", entity_id=None, meta={
        "customer_id": sale.customer_id,
        "items": len(items),
        "total": float(total),
        "paid_total": float(paid_total),
    }))

    await db.commit()
    await db.refresh(sale)
    return {"sale_id": sale.id, "status": sale.status, "total": float(sale.total_amount)}


@router.post("/{sale_id}/attachments", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def upload_sale_attachment(sale_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    path, sha256 = await save_upload("sales", file.filename, file)
    rel = str(path.relative_to(get_media_root()))
    att = SaleAttachment(
        sale_id=sale_id,
        filename=file.filename,
        mime=file.content_type or None,
        size=path.stat().st_size,
        path=rel,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return {"attachment_id": att.id, "path": att.path}
