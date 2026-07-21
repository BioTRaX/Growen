#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: customers.py
# NG-HEADER: Ubicacion: services/routers/customers.py
# NG-HEADER: Descripcion: Endpoints de clientes (CRUD, busqueda y ventas asociadas)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from decimal import Decimal
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case, literal

from db.session import get_session
from db.models import Customer, CustomerAccountEntry, Return, Sale, SalePayment, AuditLog
from services.auth import require_roles, require_csrf, current_session, SessionData
from services.sales.domain import account_balance, add_account_entry, money
from services.sales.schemas import AccountAdjustmentInput

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
    order: str = Query("name", pattern="^(name|-name|created_at|-created_at)$"),
    db: AsyncSession = Depends(get_session),
):
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    ordering = {
        "name": Customer.name.asc(),
        "-name": Customer.name.desc(),
        "created_at": Customer.created_at.asc(),
        "-created_at": Customer.created_at.desc(),
    }[order]
    stmt = select(Customer).order_by(ordering)
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
            "credit_limit": float(c.credit_limit) if c.credit_limit is not None else None,
        }

    return {
        "items": [_serialize(c) for c in rows],
        "total": int(total or 0),
        "page": page,
        "pages": ((int(total or 0) + page_size - 1) // page_size) if total else 0,
    }


@router.post("", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_customer(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
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
        credit_limit=(money(payload.get("credit_limit")) if payload.get("credit_limit") is not None else None),
    )
    db.add(c)
    await db.flush()
    _audit(db, "customer_create", "customers", c.id, {"name": c.name}, sess, request)
    await db.commit()
    await db.refresh(c)
    return {"id": c.id}


@router.patch("/{cid}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
@router.put("/{cid}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def update_customer(
    cid: int,
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
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
    if "credit_limit" in payload:
        c.credit_limit = money(payload.get("credit_limit")) if payload.get("credit_limit") is not None else None
    _audit(db, "customer_update", "customers", c.id, {"fields": sorted(payload)}, sess, request)
    await db.commit()
    return {"status": "ok"}


@router.post("/{cid}/reactivate", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def reactivate_customer(
    cid: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    customer = await db.get(Customer, cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    customer.is_active = True
    _audit(db, "customer_reactivate", "customers", cid, {}, sess, request)
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


@router.get("/segments", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def customer_segments(db: AsyncSession = Depends(get_session)):
    rows = (
        await db.execute(
            select(
                Customer.id,
                Customer.name,
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.max(Sale.sale_date),
            )
            .outerjoin(
                Sale,
                (Sale.customer_id == Customer.id) & Sale.status.in_(["CONFIRMADA", "ENTREGADA"]),
            )
            .where(Customer.is_active == True)
            .group_by(Customer.id, Customer.name)
            .order_by(func.sum(Sale.total_amount).desc().nulls_last())
        )
    ).all()
    items = []
    now = __import__("datetime").datetime.utcnow()
    for customer_id, name, frequency, amount, last_sale in rows:
        recency_days = (now - last_sale).days if last_sale else None
        segment = "nuevo"
        if frequency >= 5 and recency_days is not None and recency_days <= 90:
            segment = "frecuente"
        elif recency_days is not None and recency_days > 180:
            segment = "inactivo"
        elif Decimal(str(amount or 0)) >= Decimal("100000"):
            segment = "alto_valor"
        items.append({
            "customer_id": customer_id,
            "name": name,
            "segment": segment,
            "recency_days": recency_days,
            "frequency": int(frequency or 0),
            "amount": float(amount or 0),
        })
    return {"items": items, "total": len(items)}


@router.get("/{cid}", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_customer(cid: int, db: AsyncSession = Depends(get_session)):
    """Obtener un cliente específico con su total bruto de compras."""
    c = await db.get(Customer, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    # Calcular total bruto de compras (ventas confirmadas/entregadas)
    total_stmt = select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
        Sale.customer_id == cid,
        Sale.status.in_(["CONFIRMADA", "ENTREGADA"])
    )
    total_bruto = await db.scalar(total_stmt) or 0
    returns_total = await db.scalar(
        select(func.coalesce(func.sum(Return.total_amount), 0))
        .join(Sale, Sale.id == Return.sale_id)
        .where(Sale.customer_id == cid, Return.status == "REGISTRADA")
    ) or 0
    paid_total = await db.scalar(
        select(func.coalesce(func.sum(SalePayment.amount), 0))
        .join(Sale, Sale.id == SalePayment.sale_id)
        .where(Sale.customer_id == cid)
    ) or 0
    sale_stats = (
        await db.execute(
            select(func.count(Sale.id), func.avg(Sale.total_amount), func.max(Sale.sale_date)).where(
                Sale.customer_id == cid,
                Sale.status.in_(["CONFIRMADA", "ENTREGADA"]),
            )
        )
    ).one()
    balance = await account_balance(db, cid)
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "city": c.city,
        "province": c.province,
        "doc_id": c.doc_id,
        "document_type": c.document_type,
        "document_number": c.document_number,
        "kind": c.kind,
        "notes": c.notes,
        "is_active": bool(getattr(c, "is_active", True)),
        "total_compras_bruto": float(total_bruto),
        "credit_limit": float(c.credit_limit) if c.credit_limit is not None else None,
        "metrics": {
            "gross_sales": float(total_bruto),
            "returns_total": float(returns_total),
            "net_sales": float(Decimal(str(total_bruto)) - Decimal(str(returns_total))),
            "paid_total": float(paid_total),
            "account_balance": float(balance),
            "sale_count": int(sale_stats[0] or 0),
            "average_ticket": float(sale_stats[1] or 0),
            "last_sale_at": sale_stats[2].isoformat() if sale_stats[2] else None,
        },
    }


@router.get("/{cid}/account", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_customer_account(
    cid: int,
    page: int = 1,
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    customer = await db.get(Customer, cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    page = max(1, page)
    base = select(CustomerAccountEntry).where(CustomerAccountEntry.customer_id == cid)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = (
        await db.execute(
            base.order_by(CustomerAccountEntry.occurred_at.desc(), CustomerAccountEntry.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()
    balance = await account_balance(db, cid)
    credit_available = None
    if customer.credit_limit is not None:
        credit_available = max(Decimal("0"), Decimal(str(customer.credit_limit)) - balance)
    return {
        "balance": float(balance),
        "credit_limit": float(customer.credit_limit) if customer.credit_limit is not None else None,
        "credit_available": float(credit_available) if credit_available is not None else None,
        "items": [
            {
                "id": row.id,
                "entry_type": row.entry_type,
                "amount": float(row.amount),
                "source_type": row.source_type,
                "source_id": row.source_id,
                "note": row.note,
                "occurred_at": row.occurred_at.isoformat(),
            }
            for row in rows
        ],
        "total": int(total),
        "page": page,
        "pages": (int(total) + page_size - 1) // page_size if total else 0,
    }


@router.post(
    "/{cid}/account/adjustments",
    dependencies=[Depends(require_roles("admin")), Depends(require_csrf)],
)
async def create_customer_account_adjustment(
    cid: int,
    payload: AccountAdjustmentInput,
    request: Request,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
):
    customer = await db.get(Customer, cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    entry_type = "ADJUSTMENT_DEBIT" if payload.kind == "debit" else "ADJUSTMENT_CREDIT"
    amount = payload.amount if payload.kind == "debit" else -payload.amount
    entry = await add_account_entry(
        db,
        customer_id=cid,
        entry_type=entry_type,
        amount=amount,
        source_type="adjustment",
        source_id=secrets.randbits(63),
        user_id=getattr(sess, "user_id", None),
        correlation_id=getattr(sess, "session_id", None),
        note=payload.reason,
    )
    await db.flush()
    _audit(db, "customer_account_adjustment", "customers", cid, {"entry_id": entry.id}, sess, request)
    await db.commit()
    return {"id": entry.id, "balance": float(await account_balance(db, cid))}
