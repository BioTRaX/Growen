#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: customers.py
# NG-HEADER: Ubicacion: services/routers/customers.py
# NG-HEADER: Descripcion: Endpoints de clientes (CRUD, busqueda y ventas asociadas)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case, literal

from db.session import get_session
from db.models import Customer, Sale, AuditLog
from services.auth import require_roles, require_csrf, current_session, SessionData

router = APIRouter(prefix="/customers", tags=["customers"])


_ALLOWED_KINDS = {None, "cf", "ri", "minorista", "mayorista"}


def _audit(
    db: AsyncSession,
    action: str,
    table: str,
    entity_id: int | None,
    meta: dict | None,
    sess: SessionData | None,
    request: Request | None,
) -> None:
    try:
        payload = dict(meta or {})
        if sess and getattr(sess, "session_id", None):
            payload.setdefault("correlation_id", getattr(sess, "session_id", None))
        ip = None
        if request and request.client:
            ip = request.client.host
        db.add(
            AuditLog(
                action=action,
                table=table,
                entity_id=entity_id,
                meta=payload,
                user_id=(sess.user_id if sess and getattr(sess, "user_id", None) else None),
                ip=ip,
            )
        )
    except Exception:
        # La auditoria no debe bloquear el flujo principal
        pass


def _normalize_doc_number(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = "".join(ch for ch in str(raw) if ch.isalnum())
    normalized = normalized.upper()
    return normalized or None


def _validate_cuit_dni(doc_type: str | None, number: str | None) -> None:
    if not number:
        return
    if doc_type and doc_type.upper() == "CUIT":
        if not (number.isdigit() and len(number) == 11):
            raise HTTPException(status_code=400, detail="CUIT debe tener 11 digitos")
    elif doc_type and doc_type.upper() == "DNI":
        if not (number.isdigit() and 7 <= len(number) <= 9):
            raise HTTPException(status_code=400, detail="DNI invalido (7-9 digitos)")
    elif doc_type:
        if len(number) < 3:
            raise HTTPException(status_code=400, detail="document_number demasiado corto")


@router.get("", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_customers(
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    kind: Optional[str] = Query(None, description="Filtrar por tipo de cliente"),
    only_active: bool = Query(True, description="Solo clientes activos"),
    db: AsyncSession = Depends(get_session),
):
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    stmt = select(Customer).order_by(Customer.name.asc())
    if only_active:
        stmt = stmt.where(Customer.is_active == True)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(like),
                Customer.email.ilike(like),
                Customer.phone.ilike(like),
                Customer.doc_id.ilike(like),
                Customer.document_number.ilike(like),
            )
        )
    if kind:
        norm_kind = kind.strip().lower()
        stmt = stmt.where(Customer.kind == norm_kind)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))).scalars().all()

    def _serialize(c: Customer) -> dict:
        return {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "doc_id": c.doc_id,
            "document_type": c.document_type,
            "document_number": c.document_number,
            "address": c.address,
            "city": c.city,
            "province": c.province,
            "kind": c.kind,
            "notes": c.notes,
            "is_active": bool(getattr(c, "is_active", True)),
        }

    return {
        "items": [_serialize(c) for c in rows],
        "total": int(total or 0),
        "page": page,
        "pages": ((int(total or 0) + page_size - 1) // page_size) if total else 0,
    }


@router.post("", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_customer(payload: dict, db: AsyncSession = Depends(get_session)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name es obligatorio")
    doc_type = (payload.get("document_type") or payload.get("doc_type") or None)
    raw_number = (payload.get("document_number") or payload.get("doc_number") or None)
    norm_number = _normalize_doc_number(raw_number)
    _validate_cuit_dni(doc_type, norm_number)
    kind = payload.get("kind")
    kind_norm = kind.strip().lower() if isinstance(kind, str) else None
    if kind_norm not in _ALLOWED_KINDS:
        if kind_norm is not None:
            raise HTTPException(status_code=400, detail="kind invalido")
        kind_norm = None
    c = Customer(
        name=name,
        email=(payload.get("email") or None),
        phone=(payload.get("phone") or None),
        doc_id=(payload.get("doc_id") or None),
        document_type=(doc_type or None),
        document_number=norm_number,
        address=(payload.get("address") or None),
        city=(payload.get("city") or None),
        province=(payload.get("province") or None),
        notes=(payload.get("notes") or None),
        kind=kind_norm,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return {"id": c.id}


@router.put("/{cid}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def update_customer(cid: int, payload: dict, db: AsyncSession = Depends(get_session)):
    c = await db.get(Customer, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="name no puede quedar vacio")
        c.name = new_name
    for field in ("email", "phone", "doc_id", "address", "city", "province", "notes"):
        if field in payload:
            setattr(c, field, payload.get(field))
    if any(k in payload for k in ("document_type", "doc_type", "document_number", "doc_number")):
        doc_type = (payload.get("document_type") or payload.get("doc_type") or c.document_type)
        raw_number = (payload.get("document_number") or payload.get("doc_number") or c.document_number)
        norm_number = _normalize_doc_number(raw_number)
        _validate_cuit_dni(doc_type, norm_number)
        c.document_type = doc_type
        c.document_number = norm_number
    if "kind" in payload:
        kind = payload.get("kind")
        kind_norm = kind.strip().lower() if isinstance(kind, str) else None
        if kind_norm not in _ALLOWED_KINDS:
            if kind_norm is not None:
                raise HTTPException(status_code=400, detail="kind invalido")
            kind_norm = None
        c.kind = kind_norm
    if "is_active" in payload:
        c.is_active = bool(payload.get("is_active"))
    await db.commit()
    return {"status": "ok"}


@router.delete("/{cid}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def delete_customer(
    cid: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    c = await db.get(Customer, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if getattr(c, "is_active", True) is False:
        return {"status": "ok", "already": True}
    c.is_active = False
    _audit(db, "customer_soft_delete", "customers", c.id, {}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.get("/{cid}/sales", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_customer_sales(cid: int, page: int = 1, page_size: int = 50, db: AsyncSession = Depends(get_session)):
    cust = await db.get(Customer, cid)
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    base = select(Sale).where(Sale.customer_id == cid).order_by(Sale.id.desc())
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (await db.execute(base.limit(page_size).offset((page - 1) * page_size))).scalars().all()

    def _serialize_sale(sale: Sale) -> dict:
        return {
            "id": sale.id,
            "status": sale.status,
            "sale_date": sale.sale_date.isoformat(),
            "total": float(sale.total_amount or 0),
            "paid_total": float(sale.paid_total or 0),
        }

    return {
        "items": [_serialize_sale(s) for s in rows],
        "total": int(total or 0),
        "page": page,
        "pages": ((int(total or 0) + page_size - 1) // page_size) if total else 0,
    }


@router.get("/search", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def quick_search_customers(q: str, limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_session)):
    term = (q or "").strip()
    if term == "":
        raise HTTPException(status_code=400, detail="q requerido")
    like_any = f"%{term}%"
    like_prefix = f"{term}%"
    weight = case(
        (Customer.document_number == term, literal(100)),
        (Customer.name.ilike(like_prefix), literal(90)),
        (Customer.name.ilike(like_any), literal(70)),
        (Customer.email.ilike(like_any), literal(60)),
        (Customer.phone.ilike(like_any), literal(50)),
        (Customer.doc_id.ilike(like_any), literal(40)),
        else_=literal(0),
    ).label("weight")
    query = (
        select(Customer, weight)
        .where(Customer.is_active == True)
        .where(
            or_(
                Customer.document_number == term,
                Customer.name.ilike(like_any),
                Customer.email.ilike(like_any),
                Customer.phone.ilike(like_any),
                Customer.doc_id.ilike(like_any),
            )
        )
        .order_by(weight.desc(), Customer.name.asc())
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    items = []
    for customer, score in rows:
        items.append(
            {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "document_type": customer.document_type,
                "document_number": customer.document_number,
                "kind": customer.kind,
                "weight": int(score or 0),
            }
        )
    return {"query": term, "items": items, "count": len(items)}
