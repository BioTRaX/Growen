# NG-HEADER: Nombre de archivo: sales.py
# NG-HEADER: Ubicación: services/routers/sales.py
# NG-HEADER: Descripción: Endpoints de clientes y ventas (CRUD clientes, registrar venta, adjuntos)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional
from datetime import datetime
import logging
import os
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, Float

from db.session import get_session
from db.models import Customer, Sale, SaleLine, SalePayment, SaleAttachment, Product, AuditLog, Return, ReturnLine
from db.models import StockLedger, SalesChannel, StockReservation, SupplierProduct
from services.auth import require_roles, require_csrf, current_session, SessionData
from services.media import save_upload, get_media_root
from services.sales.domain import (
    account_balance,
    add_account_entry,
    expire_reservations,
    money,
    quantity,
    recalculate_sale_totals,
    reservation_expiry,
)
from services.sales.schemas import SaleQuoteRequest
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from sqlalchemy import desc

router = APIRouter(prefix="/sales", tags=["sales"])
logger = logging.getLogger(__name__)

# --- Cache simple in-memory para reportes agregados ---
# Nota: proceso single-worker; si se despliega multi-proceso o distribuido conviene backend compartido (Redis).
_REPORT_CACHE: dict[str, dict] = {}
_REPORT_CACHE_TTL_SECONDS = 60  # TTL por defecto (optimizable)

def _report_cache_key(kind: str, **params) -> str:
    items = sorted((k, str(v)) for k, v in params.items())
    return kind + "|" + "&".join(f"{k}={v}" for k, v in items)

def _report_cache_get(key: str):
    import time as _t
    entry = _REPORT_CACHE.get(key)
    if not entry:
        return None
    if entry["expires"] < _t.time():
        _REPORT_CACHE.pop(key, None)
        return None
    return entry["data"]

def _report_cache_set(key: str, data: dict, ttl: int | None = None):
    import time as _t
    _REPORT_CACHE[key] = {"data": data, "expires": _t.time() + (ttl or _REPORT_CACHE_TTL_SECONDS)}

def _report_cache_invalidate():
    _REPORT_CACHE.clear()


def _iter_sales_csv(rows):
    import csv, io
    header = ["id","sale_date","status","sale_kind","customer_id","subtotal","discount_amount","tax","total_amount","paid_total","payment_status"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    yield buf.getvalue()
    buf.seek(0); buf.truncate(0)
    for s in rows:
        writer.writerow([
            s.id,
            s.sale_date.isoformat(),
            s.status,
            s.sale_kind,
            s.customer_id,
            float(s.subtotal or 0),
            float(s.discount_amount or 0),
            float(s.tax or 0),
            float(s.total_amount or 0),
            float(s.paid_total or 0),
            s.payment_status or None,
        ])
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)


# --- Helper auditoría unificada ---
def _audit(db: AsyncSession, action: str, table: str, entity_id: int | None, meta: dict | None, sess: SessionData | None, request: Request | None):
    try:
        full_meta = dict(meta or {})
        if sess and getattr(sess, "session_id", None):
            full_meta.setdefault("correlation_id", getattr(sess, "session_id", None))
        ip = None
        if request and request.client:
            ip = request.client.host
        db.add(AuditLog(
            action=action,
            table=table,
            entity_id=entity_id,
            meta=full_meta,
            user_id=(sess.user_id if sess and getattr(sess, "user_id", None) else None),
            ip=ip,
        ))
    except Exception:
        # Falla silenciosa para no romper flujo principal
        pass




# --- Canales de Venta ---

@router.get("/channels", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_channels(db: AsyncSession = Depends(get_session)):
    """Lista todos los canales de venta disponibles."""
    channels = (await db.execute(select(SalesChannel).order_by(SalesChannel.name))).scalars().all()
    return {
        "items": [{"id": c.id, "name": c.name, "created_at": c.created_at.isoformat()} for c in channels],
        "total": len(channels)
    }


@router.post("/channels", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_channel(payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    """Crea un nuevo canal de venta."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name es requerido")
    # Verificar si ya existe
    existing = (await db.execute(select(SalesChannel).where(SalesChannel.name == name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un canal con ese nombre")
    channel = SalesChannel(name=name)
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    _audit(db, "channel_create", "sales_channels", channel.id, {"name": name}, sess, request)
    await db.commit()
    return {"id": channel.id, "name": channel.name, "created_at": channel.created_at.isoformat()}


@router.delete("/channels/{channel_id}", dependencies=[Depends(require_roles("admin")), Depends(require_csrf)])
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    """Elimina un canal de venta (solo admin)."""
    channel = await db.get(SalesChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    name = channel.name
    await db.delete(channel)
    _audit(db, "channel_delete", "sales_channels", channel_id, {"name": name}, sess, request)
    await db.commit()
    return {"status": "deleted", "id": channel_id}


# --- Ventas ---


def _recalc_totals(db_sale: Sale, lines: list[SaleLine]) -> None:
    recalculate_sale_totals(db_sale, lines)


"""Rate limiting simple (in-memory). Nota: mono-proceso; usar Redis en despliegues multi.
_RL_BUCKET almacena timestamps por llave (usuario o IP)."""
_RL_BUCKET: dict[str, list[float]] = {}
_RL_MAX = max(1, int(os.getenv("SALES_RATE_LIMIT_PER_MINUTE", "30")))
_RL_WINDOW = 60  # segundos

def _rl_check(key: str):
    import time as _t
    now = _t.time()
    bucket = _RL_BUCKET.setdefault(key, [])
    cutoff = now - _RL_WINDOW
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    # Si ya alcanzó el máximo, bloquear antes de agregar
    if len(bucket) >= _RL_MAX:
        return False, int(bucket[0] + _RL_WINDOW - now)
    bucket.append(now)
    return True, None


async def _rl_check_configured(key: str) -> tuple[bool, int | None]:
    if os.getenv("SALES_RATE_LIMIT_BACKEND", "memory").strip().lower() != "redis":
        return _rl_check(key)
    try:
        import redis.asyncio as aioredis

        now = int(time.time())
        redis_key = f"growen:sales:rate:{key}:{now // 60}"
        client = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        try:
            count = await client.incr(redis_key)
            if count == 1:
                await client.expire(redis_key, 61)
        finally:
            await client.aclose()
        return count <= _RL_MAX, max(1, 60 - (now % 60))
    except Exception as exc:
        logger.error("Rate limit Redis no disponible: %s", exc)
        raise HTTPException(status_code=503, detail={"code": "rate_limit_unavailable"}) from exc


def _normalize_payment_method(m: Optional[str]) -> str:
    """Normaliza métodos de pago libres a enumeración soportada.

    Tests usan 'tarjeta' pero constraint histórica sólo contemplaba 'credito'.
    Mapeamos 'tarjeta' -> 'credito'. Otros valores desconocidos => 'otro'.
    """
    m = (m or "efectivo").lower()
    if m == "tarjeta":
        return "credito"
    allowed = {"efectivo","debito","credito","transferencia","mercadopago","otro"}
    return m if m in allowed else "otro"


@router.post("/quote", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def quote_sale(payload: SaleQuoteRequest, db: AsyncSession = Depends(get_session)):
    """Calcula una venta sin persistirla; comparte exactamente las reglas del guardado."""
    sale = Sale(
        discount_percent=payload.discount_percent,
        discount_amount=payload.discount_amount,
        additional_costs=[cost.model_dump(mode="json") for cost in payload.additional_costs],
        tax=payload.tax,
        subtotal=Decimal("0"),
        total_amount=Decimal("0"),
        paid_total=Decimal("0"),
    )
    lines: list[SaleLine] = []
    for item in payload.items:
        product = await db.get(Product, item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
        unit_price = item.unit_price
        if unit_price is None:
            unit_price = Decimal(str(product.variants[0].price if product.variants else 0))
        if unit_price <= 0:
            raise HTTPException(status_code=422, detail=f"Producto {item.product_id} no tiene precio de venta")
        lines.append(
            SaleLine(
                product_id=item.product_id,
                qty=item.qty,
                unit_price=unit_price,
                line_discount=item.line_discount,
            )
        )
    totals = recalculate_sale_totals(sale, lines)
    return {
        **{key: float(value) for key, value in totals.items()},
        "lines": [
            {
                "product_id": line.product_id,
                "qty": float(line.qty),
                "unit_price": float(line.unit_price),
                "subtotal": float(line.subtotal or 0),
                "total": float(line.total or 0),
            }
            for line in lines
        ],
    }


@router.post("", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_sale(
    payload: dict,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    request: Request = None,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=128),
):
    """Crea una venta en BORRADOR (por defecto) sin afectar stock hasta confirmar.

    payload:
      - customer: datos o id
      - items: líneas iniciales (opcional, se pueden agregar luego)
      - payments: pagos iniciales (raro en BORRADOR, permitido si se desea)
      - discount_percent / discount_amount
      - status: 'BORRADOR' | 'CONFIRMADA' (si llega CONFIRMADA valida stock y afecta)
    """
    # Rate limiting siempre activo. Se puede desactivar sólo si SALES_RATE_LIMIT_DISABLED=1 (uso puntual local)
    try:
        import os
        if os.getenv("SALES_RATE_LIMIT_DISABLED") not in ("1","true","True"):
            key = "global"
            if request is not None:
                uid = getattr(sess, 'user_id', None)
                if uid:
                    key = f"u:{uid}"
                elif request.client:
                    key = f"ip:{request.client.host}"
            # Bucket global módulo
            ok, retry = await _rl_check_configured(key)
            if not ok:
                raise HTTPException(status_code=429, detail={"code": "rate_limited", "retry_in": retry})
            # Bucket alternativo ligado a la app (por si en tests se aísla el módulo)
            if request is not None:
                store = getattr(request.app.state, "_sales_rl_bucket", None)
                if store is None:
                    store = {}
                    request.app.state._sales_rl_bucket = store
                import time as _t
                now = _t.time()
                win = _RL_WINDOW
                bucket2 = store.setdefault(key, [])
                cutoff = now - win
                # limpiar expirados
                bucket2[:] = [t for t in bucket2 if t >= cutoff]
                if len(bucket2) >= _RL_MAX:
                    retry2 = int((bucket2[0] + win) - now)
                    raise HTTPException(status_code=429, detail={"code": "rate_limited", "retry_in": retry2})
                bucket2.append(now)
    except HTTPException:
        raise
    except Exception:
        pass

    t0 = time.perf_counter()
    if idempotency_key:
        existing = await db.scalar(select(Sale).where(Sale.idempotency_key == idempotency_key))
        if existing:
            return {
                "sale_id": existing.id,
                "status": existing.status,
                "total": float(existing.total_amount or 0),
                "idempotent_replay": True,
            }
    customer_payload = payload.get("customer") or {}
    items = payload.get("items") or []
    payments = payload.get("payments") or []
    status_req = (payload.get("status") or "BORRADOR").upper()
    if status_req not in ("BORRADOR", "CONFIRMADA"):
        status_req = "BORRADOR"
    sale_kind = (payload.get("sale_kind") or "MOSTRADOR").upper()
    if sale_kind not in ("MOSTRADOR", "PEDIDO"):
        sale_kind = "MOSTRADOR"

    # Canal de venta
    channel_id = payload.get("channel_id")
    if channel_id is not None:
        channel = await db.get(SalesChannel, int(channel_id))
        if not channel:
            raise HTTPException(status_code=400, detail="Canal de venta no existe")
        channel_id = channel.id

    # Costos adicionales (validar estructura)
    additional_costs = payload.get("additional_costs")
    if additional_costs is not None:
        if not isinstance(additional_costs, list):
            raise HTTPException(status_code=400, detail="additional_costs debe ser una lista")
        for i, cost in enumerate(additional_costs):
            if not isinstance(cost, dict) or "concept" not in cost or "amount" not in cost:
                raise HTTPException(status_code=400, detail=f"additional_costs[{i}] debe tener 'concept' y 'amount'")
            try:
                Decimal(str(cost["amount"]))
            except Exception:
                raise HTTPException(status_code=400, detail=f"additional_costs[{i}].amount inválido")

    # Cliente
    customer_id: Optional[int] = customer_payload.get("id") if isinstance(customer_payload, dict) else None
    customer_obj: Optional[Customer] = None
    if customer_id:
        customer_obj = await db.get(Customer, int(customer_id))
        if not customer_obj:
            raise HTTPException(status_code=400, detail="Cliente no existe")
    elif customer_payload:
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
        channel_id=channel_id,
        status="BORRADOR",  # se ajustará si se confirma
        sale_date=datetime.fromisoformat(payload.get("sale_date")) if payload.get("sale_date") else datetime.utcnow(),
        sale_kind=sale_kind,
        additional_costs=additional_costs,
        idempotency_key=idempotency_key,
        note=(payload.get("note") or None),
        created_by=sess.user_id if getattr(sess, "user_id", None) else None,
        discount_percent=(payload.get("discount_percent") or 0),
        discount_amount=(payload.get("discount_amount") or 0),
        subtotal=Decimal("0"),
        total_amount=Decimal("0"),
    )
    db.add(sale)
    await db.flush()

    items = payload.get("items") or []
    payments = payload.get("payments") or []
    created_lines: list[SaleLine] = []
    for it in items:
        pid = int(it.get("product_id"))
        qty = quantity(it.get("qty"))
        prod = await db.get(Product, pid)
        if not prod:
            raise HTTPException(status_code=400, detail=f"Producto {pid} no encontrado")
        unit_price = Decimal(str(it.get("unit_price") or 0)) or Decimal(str(prod.variants[0].price if prod.variants else 0))
        if unit_price <= 0:
            raise HTTPException(status_code=400, detail="unit_price debe ser > 0")
        line_discount = Decimal(str(it.get("line_discount") or 0))
        if line_discount < 0 or line_discount > 100:
            raise HTTPException(status_code=400, detail="line_discount debe estar entre 0 y 100")
        sl = SaleLine(
            sale_id=sale.id,
            product_id=pid,
            qty=qty,
            unit_price=unit_price,
            line_discount=line_discount,
        )
        db.add(sl)
        created_lines.append(sl)

    # Pagos iniciales
    paid_total = Decimal("0")
    for p in payments:
        amount = Decimal(str(p.get("amount") or 0))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="payment amount debe ser > 0")
        method_norm = _normalize_payment_method(p.get("method"))
        sp = SalePayment(
            sale_id=sale.id,
            method=method_norm,
            amount=amount,
            reference=(p.get("reference") or None),
        )
        db.add(sp)
        paid_total += amount
    sale.paid_total = paid_total

    await db.flush()
    initial_payments = (
        await db.execute(select(SalePayment).where(SalePayment.sale_id == sale.id))
    ).scalars().all()
    for payment in initial_payments:
        await add_account_entry(
            db,
            customer_id=sale.customer_id,
            entry_type="PAYMENT",
            amount=-money(payment.amount),
            source_type="payment",
            source_id=payment.id,
            user_id=getattr(sess, "user_id", None),
            correlation_id=getattr(sess, "session_id", None),
            note=payment.reference,
        )
    lines_full = (await db.execute(select(SaleLine).where(SaleLine.sale_id == sale.id))).scalars().all()
    _recalc_totals(sale, lines_full)

    # Confirmar inmediatamente si se solicitó
    if status_req == "CONFIRMADA":
        missing = []
        for l in lines_full:
            prod = await db.get(Product, l.product_id)
            if Decimal(str(prod.stock or 0)) < Decimal(str(l.qty)):
                missing.append({"product_id": prod.id, "needed": float(l.qty), "have": float(prod.stock or 0)})
        if missing:
            raise HTTPException(status_code=400, detail={"error": "stock_insuficiente", "items": missing})
        for l in lines_full:
            prod = await db.get(Product, l.product_id)
            before = Decimal(str(prod.stock or 0))
            prod.stock = before - Decimal(str(l.qty))
            db.add(StockLedger(
                product_id=prod.id,
                source_type="sale",
                source_id=sale.id,
                delta=-Decimal(str(l.qty)),
                balance_after=prod.stock,
                meta={"sale_line_id": l.id, "immediate": True},
            ))
        sale.status = "CONFIRMADA"
        await add_account_entry(
            db,
            customer_id=sale.customer_id,
            entry_type="SALE_CHARGE",
            amount=money(sale.total_amount),
            source_type="sale",
            source_id=sale.id,
            user_id=getattr(sess, "user_id", None),
            correlation_id=getattr(sess, "session_id", None),
        )
        _report_cache_invalidate()
        _audit(db, "sale_confirm", "sales", sale.id, {"immediate": True}, sess, request)
    else:
        sale.status = "BORRADOR"

    _audit(db, "sale_create", "sales", sale.id, {
        "customer_id": sale.customer_id,
        "items": len(lines_full),
        "total": float(sale.total_amount or 0),
        "paid_total": float(sale.paid_total or 0),
        "status": sale.status,
        "elapsed_ms": round((time.perf_counter()-t0)*1000,2),
    }, sess, request)

    await db.commit()
    await db.refresh(sale)
    return {"sale_id": sale.id, "status": sale.status, "total": float(sale.total_amount)}


@router.post("/{sale_id}/lines", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def sale_lines_ops(sale_id: int, payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    """Opera sobre líneas de una venta en BORRADOR.

    payload: { ops: [ {op: add|update|remove, ...} ] }
      add:    product_id, qty (>0), unit_price (>0), line_discount (0-100 opcional)
      update: line_id, (qty|unit_price|line_discount)
      remove: line_id

    Retorna totales recalculados.
    """
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if sale.status != "BORRADOR":
        raise HTTPException(status_code=400, detail="Sólo editable en BORRADOR")
    await expire_reservations(db, sale.id)
    active_reservation = await db.scalar(
        select(StockReservation.id).where(
            StockReservation.sale_id == sale.id,
            StockReservation.status == "ACTIVE",
            StockReservation.expires_at > datetime.utcnow(),
        ).limit(1)
    )
    if active_reservation:
        raise HTTPException(status_code=409, detail={"code": "sale_reserved", "message": "Liberar la reserva antes de editar"})
    ops = payload.get("ops") or []
    if not ops:
        raise HTTPException(status_code=400, detail="ops requerido")
    audit_ops: list[dict] = []
    from decimal import Decimal as _D
    for op in ops:
        kind = (op.get("op") or "").lower()
        if kind == "add":
            pid = op.get("product_id")
            qty = op.get("qty")
            if pid is None or qty is None:
                raise HTTPException(status_code=400, detail="product_id y qty requeridos")
            qty_d = quantity(qty)
            prod = await db.get(Product, int(pid))
            if not prod:
                raise HTTPException(status_code=400, detail="Producto no encontrado")
            unit_price = _D(str(op.get("unit_price") or 0)) or _D(str(prod.variants[0].price if prod.variants else 0))
            if unit_price <= 0:
                raise HTTPException(status_code=400, detail="unit_price debe ser > 0")
            line_discount = _D(str(op.get("line_discount") or 0))
            if line_discount < 0 or line_discount > 100:
                raise HTTPException(status_code=400, detail="line_discount inválido")
            sl = SaleLine(
                sale_id=sale.id,
                product_id=prod.id,
                qty=qty_d,
                unit_price=unit_price,
                line_discount=line_discount,
            )
            db.add(sl)
            await db.flush()
            audit_ops.append({"op": "add", "line_id": sl.id, "product_id": prod.id, "qty": float(sl.qty)})
        elif kind == "update":
            line_id = op.get("line_id")
            if line_id is None:
                raise HTTPException(status_code=400, detail="line_id requerido para update")
            line = await db.get(SaleLine, int(line_id))
            if not line or line.sale_id != sale.id:
                raise HTTPException(status_code=404, detail="Línea no encontrada")
            changed = []
            if "qty" in op:
                qv = quantity(op.get("qty"))
                line.qty = qv; changed.append("qty")
            if "unit_price" in op:
                up = _D(str(op.get("unit_price") or 0))
                if up <= 0:
                    raise HTTPException(status_code=400, detail="unit_price debe ser > 0")
                line.unit_price = up; changed.append("unit_price")
            if "line_discount" in op:
                ld = _D(str(op.get("line_discount") or 0))
                if ld < 0 or ld > 100:
                    raise HTTPException(status_code=400, detail="line_discount inválido")
                line.line_discount = ld; changed.append("line_discount")
            if changed:
                audit_ops.append({"op": "update", "line_id": line.id, "fields": changed})
        elif kind == "remove":
            line_id = op.get("line_id")
            if line_id is None:
                raise HTTPException(status_code=400, detail="line_id requerido para remove")
            line = await db.get(SaleLine, int(line_id))
            if not line or line.sale_id != sale.id:
                raise HTTPException(status_code=404, detail="Línea no encontrada")
            await db.delete(line)
            audit_ops.append({"op": "remove", "line_id": int(line_id)})
        else:
            raise HTTPException(status_code=400, detail=f"op desconocida {kind}")
    await db.flush()
    lines_full = (await db.execute(select(SaleLine).where(SaleLine.sale_id == sale.id))).scalars().all()
    _recalc_totals(sale, lines_full)
    _audit(db, "sale_lines_ops", "sales", sale.id, {"ops": audit_ops, "lines_total": len(lines_full), "total_amount": float(sale.total_amount or 0)}, sess, request)
    await db.commit()
    return {"status": "ok", "total": float(sale.total_amount or 0), "lines": len(lines_full), "ops": len(audit_ops)}


@router.patch("/{sale_id}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def patch_sale(sale_id: int, payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if sale.status != "BORRADOR":
        raise HTTPException(status_code=400, detail="Sólo editable en BORRADOR")
    changed = []
    if "discount_percent" in payload:
        dp = Decimal(str(payload.get("discount_percent") or 0))
        if dp < 0 or dp > 100:
            raise HTTPException(status_code=400, detail="discount_percent debe estar entre 0 y 100")
        sale.discount_percent = dp
        changed.append("discount_percent")
        # reset discount_amount si se proporciona un percent
        sale.discount_amount = Decimal("0")
    if "discount_amount" in payload:
        da = Decimal(str(payload.get("discount_amount") or 0))
        if da < 0:
            raise HTTPException(status_code=400, detail="discount_amount inválido")
        sale.discount_amount = da
        changed.append("discount_amount")
        # si se usa monto directo, sobrescribir percent
        sale.discount_percent = Decimal("0")
    if "note" in payload:
        sale.note = (payload.get("note") or None)
        changed.append("note")
    if "sale_kind" in payload:
        sale_kind = str(payload.get("sale_kind") or "").upper()
        if sale_kind not in ("MOSTRADOR", "PEDIDO"):
            raise HTTPException(status_code=422, detail="sale_kind inválido")
        sale.sale_kind = sale_kind
        changed.append("sale_kind")
    if "customer_id" in payload:
        cid = payload.get("customer_id")
        if cid is not None:
            c = await db.get(Customer, int(cid))
            if not c:
                raise HTTPException(status_code=400, detail="customer_id inválido")
            sale.customer_id = c.id
            changed.append("customer_id")
    if "channel_id" in payload:
        ch_id = payload.get("channel_id")
        if ch_id is not None:
            ch = await db.get(SalesChannel, int(ch_id))
            if not ch:
                raise HTTPException(status_code=400, detail="channel_id inválido")
            sale.channel_id = ch.id
        else:
            sale.channel_id = None
        changed.append("channel_id")
    if "additional_costs" in payload:
        ac = payload.get("additional_costs")
        if ac is not None:
            if not isinstance(ac, list):
                raise HTTPException(status_code=400, detail="additional_costs debe ser una lista")
            for i, cost in enumerate(ac):
                if not isinstance(cost, dict) or "concept" not in cost or "amount" not in cost:
                    raise HTTPException(status_code=400, detail=f"additional_costs[{i}] debe tener 'concept' y 'amount'")
                try:
                    Decimal(str(cost["amount"]))
                except Exception:
                    raise HTTPException(status_code=400, detail=f"additional_costs[{i}].amount inválido")
        sale.additional_costs = ac
        changed.append("additional_costs")
    await db.flush()
    lines_full = (await db.execute(select(SaleLine).where(SaleLine.sale_id == sale.id))).scalars().all()
    _recalc_totals(sale, lines_full)
    _audit(db, "sale_patch", "sales", sale.id, {"fields": changed}, sess, request)
    await db.commit()
    return {"status": "ok", "total": float(sale.total_amount or 0), "fields": changed}




# --- Ventas: listado y detalle ---

@router.get("", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_sales(
    status: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    channel_id: Optional[int] = Query(None),
    dt_from: Optional[str] = Query(None),
    dt_to: Optional[str] = Query(None),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_session),
):
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    stmt = select(Sale).order_by(Sale.id.desc())
    if status:
        stmt = stmt.where(Sale.status == status)
    if payment_status:
        stmt = stmt.where(Sale.payment_status == payment_status)
    if customer_id:
        stmt = stmt.where(Sale.customer_id == int(customer_id))
    if channel_id:
        stmt = stmt.where(Sale.channel_id == int(channel_id))
    from datetime import datetime as _dt
    if dt_from:
        try:
            d = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date >= d)
        except Exception:
            pass
    if dt_to:
        try:
            d = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date <= d)
        except Exception:
            pass
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.execute(stmt.limit(page_size).offset((page-1)*page_size))).scalars().all()
    customer_ids = {row.customer_id for row in rows if row.customer_id is not None}
    channel_ids = {row.channel_id for row in rows if row.channel_id is not None}
    customer_names = dict((await db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids)))).all()) if customer_ids else {}
    channel_names = dict((await db.execute(select(SalesChannel.id, SalesChannel.name).where(SalesChannel.id.in_(channel_ids)))).all()) if channel_ids else {}
    def _row(s: Sale):
        return {
            "id": s.id,
            "status": s.status,
            "sale_date": s.sale_date.isoformat(),
            "sale_kind": s.sale_kind,
            "customer_id": s.customer_id,
            "customer_name": customer_names.get(s.customer_id),
            "channel_id": s.channel_id,
            "channel_name": channel_names.get(s.channel_id),
            "payment_status": s.payment_status,
            "total": float(s.total_amount or 0),
            "paid_total": float(s.paid_total or 0),
            "balance": float(max(Decimal("0"), Decimal(str(s.total_amount or 0)) - Decimal(str(s.paid_total or 0)))),
        }
    return {"items": [_row(s) for s in rows], "total": int(total or 0), "page": page, "pages": ((int(total or 0) + page_size - 1)//page_size) if total else 0}


# --- Productos para ventas (lista simple) ---
# IMPORTANTE: Este endpoint DEBE estar antes de /{sale_id} para evitar conflictos de rutas
@router.get("/products", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_products_for_sales(
    stock_gt: int = Query(0, description="Filtrar por stock mayor a este valor"),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_session)
):
    """Lista productos con stock disponible para usar en el POS de ventas."""
    from db.models import SupplierProduct, ProductEquivalence, CanonicalProduct
    
    # Primero obtener productos con stock
    stmt = (
        select(Product)
        .where(Product.stock > stock_gt)
        .order_by(Product.title)
        .limit(limit)
    )
    products = (await db.execute(stmt)).scalars().all()
    
    await expire_reservations(db)
    reserved_rows = (
        await db.execute(
            select(StockReservation.product_id, func.sum(StockReservation.qty))
            .where(
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.utcnow(),
            )
            .group_by(StockReservation.product_id)
        )
    ).all()
    reserved_by_product = {product_id: Decimal(str(qty or 0)) for product_id, qty in reserved_rows}
    items = []
    for p in products:
        price = None
        
        # 1. Intentar obtener canonical_sale_price (prioridad, igual que Stock)
        canonical_stmt = (
            select(CanonicalProduct.sale_price)
            .join(ProductEquivalence, ProductEquivalence.canonical_product_id == CanonicalProduct.id)
            .join(SupplierProduct, SupplierProduct.id == ProductEquivalence.supplier_product_id)
            .where(SupplierProduct.internal_product_id == p.id)
            .where(CanonicalProduct.sale_price.is_not(None))
            .limit(1)
        )
        canonical_price = (await db.execute(canonical_stmt)).scalar_one_or_none()
        
        if canonical_price is not None:
            price = float(canonical_price)
        else:
            # 2. Si no hay precio canónico, usar current_sale_price del SupplierProduct
            supplier_stmt = (
                select(SupplierProduct.current_sale_price)
                .where(SupplierProduct.internal_product_id == p.id)
                .where(SupplierProduct.current_sale_price.is_not(None))
                .order_by(SupplierProduct.last_seen_at.desc().nulls_last())
                .limit(1)
            )
            supplier_price = (await db.execute(supplier_stmt)).scalar_one_or_none()
            if supplier_price is not None:
                price = float(supplier_price)
        
        items.append({
            "id": p.id,
            "title": p.title,
            "sku": p.sku_root,
            "stock": float(Decimal(str(p.stock or 0)) - reserved_by_product.get(p.id, Decimal("0"))),
            "physical_stock": float(p.stock or 0),
            "price": price,
        })
    return {"items": items, "total": len(items)}


@router.post("/{sale_id}/reserve", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def reserve_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    request: Request = None,
):
    sale = await db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if sale.status != "BORRADOR" or sale.sale_kind != "PEDIDO":
        raise HTTPException(status_code=409, detail="Sólo se reservan pedidos en borrador")
    await expire_reservations(db, sale.id)
    existing = (
        await db.execute(
            select(StockReservation).where(
                StockReservation.sale_id == sale.id,
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.utcnow(),
            )
        )
    ).scalars().all()
    if existing:
        return {
            "sale_id": sale.id,
            "status": "ACTIVE",
            "expires_at": min(row.expires_at for row in existing).isoformat(),
            "lines": len(existing),
            "already": True,
        }
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == sale.id))).scalars().all()
    if not lines:
        raise HTTPException(status_code=422, detail="La venta no tiene líneas")
    expiry = reservation_expiry()
    missing = []
    for line in lines:
        product = await db.scalar(select(Product).where(Product.id == line.product_id).with_for_update())
        reserved = await db.scalar(
            select(func.coalesce(func.sum(StockReservation.qty), 0)).where(
                StockReservation.product_id == line.product_id,
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.utcnow(),
            )
        ) or 0
        available = Decimal(str(product.stock or 0)) - Decimal(str(reserved or 0)) if product else Decimal("0")
        if available < Decimal(str(line.qty)):
            missing.append({"product_id": line.product_id, "needed": float(line.qty), "have": float(available)})
    if missing:
        raise HTTPException(status_code=409, detail={"error": "stock_insuficiente", "items": missing})
    customer = await db.get(Customer, sale.customer_id) if sale.customer_id else None
    if customer and customer.credit_limit is not None:
        projected = await account_balance(db, customer.id) + money(sale.total_amount)
        if projected > Decimal(str(customer.credit_limit)):
            raise HTTPException(status_code=409, detail={"code": "credit_limit_exceeded", "projected": float(projected)})
    for line in lines:
        db.add(StockReservation(
            sale_id=sale.id,
            sale_line_id=line.id,
            product_id=line.product_id,
            qty=line.qty,
            expires_at=expiry,
        ))
    _audit(db, "sale_reserve", "sales", sale.id, {"expires_at": expiry.isoformat()}, sess, request)
    await db.commit()
    return {"sale_id": sale.id, "status": "ACTIVE", "expires_at": expiry.isoformat(), "lines": len(lines)}


@router.post("/{sale_id}/release-reservation", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def release_sale_reservation(
    sale_id: int,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    request: Request = None,
):
    sale = await db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    await expire_reservations(db, sale.id)
    rows = (
        await db.execute(
            select(StockReservation).where(
                StockReservation.sale_id == sale.id,
                StockReservation.status == "ACTIVE",
            )
        )
    ).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "RELEASED"
        row.released_at = now
    _audit(db, "sale_reservation_release", "sales", sale.id, {"lines": len(rows)}, sess, request)
    await db.commit()
    return {"sale_id": sale.id, "status": "RELEASED", "lines": len(rows)}


@router.get("/{sale_id}", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_sale_detail(sale_id: int, db: AsyncSession = Depends(get_session)):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    line_rows = (
        await db.execute(
            select(SaleLine, Product.title, Product.sku_root)
            .join(Product, Product.id == SaleLine.product_id)
            .where(SaleLine.sale_id == s.id)
            .order_by(SaleLine.id)
        )
    ).all()
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == s.id))).scalars().all()
    attachments = (await db.execute(select(SaleAttachment).where(SaleAttachment.sale_id == s.id))).scalars().all()
    returns = (await db.execute(select(Return).where(Return.sale_id == s.id).order_by(Return.id))).scalars().all()
    customer_name = await db.scalar(select(Customer.name).where(Customer.id == s.customer_id)) if s.customer_id else None
    channel_name = await db.scalar(select(SalesChannel.name).where(SalesChannel.id == s.channel_id)) if s.channel_id else None
    await expire_reservations(db, s.id)
    reservations = (
        await db.execute(select(StockReservation).where(StockReservation.sale_id == s.id).order_by(StockReservation.id))
    ).scalars().all()
    return {
        "id": s.id,
        "status": s.status,
        "sale_date": s.sale_date.isoformat(),
        "customer_id": s.customer_id,
        "customer_name": customer_name,
        "channel_id": s.channel_id,
        "channel_name": channel_name,
        "sale_kind": s.sale_kind,
        "additional_costs": s.additional_costs,
        "additional_cost_total": float(s.additional_cost_total or 0),
        "subtotal": float(s.subtotal or 0),
        "discount_amount": float(s.discount_amount or 0),
        "tax": float(s.tax or 0),
        "total": float(s.total_amount or 0),
        "paid_total": float(s.paid_total or 0),
        "payment_status": s.payment_status,
        "lines": [
            {
                "id": line.id,
                "product_id": line.product_id,
                "product_name": line.title_snapshot or product_title,
                "sku": line.sku_snapshot or sku,
                "qty": float(line.qty),
                "unit_price": float(line.unit_price),
                "line_discount": float(line.line_discount or 0),
                "subtotal": float(line.subtotal or 0),
                "total": float(line.total or 0),
                "unit_cost_snapshot": float(line.unit_cost_snapshot) if line.unit_cost_snapshot is not None else None,
            }
            for line, product_title, sku in line_rows
        ],
        "payments": [{"id": p.id, "method": p.method, "amount": float(p.amount), "reference": p.reference, "paid_at": (p.paid_at.isoformat() if p.paid_at else None)} for p in pays],
        "attachments": [
            {"id": item.id, "filename": item.filename, "mime": item.mime, "size": item.size, "path": item.path}
            for item in attachments
        ],
        "returns": [
            {"id": item.id, "status": item.status, "reason": item.reason, "total": float(item.total_amount), "created_at": item.created_at.isoformat()}
            for item in returns
        ],
        "reservations": [
            {"id": item.id, "line_id": item.sale_line_id, "qty": float(item.qty), "status": item.status, "expires_at": item.expires_at.isoformat()}
            for item in reservations
        ],
        "allowed_actions": {
            "edit": s.status == "BORRADOR" and not any(item.status == "ACTIVE" for item in reservations),
            "reserve": s.status == "BORRADOR" and s.sale_kind == "PEDIDO",
            "confirm": s.status == "BORRADOR",
            "deliver": s.status == "CONFIRMADA",
            "annul": s.status in ("CONFIRMADA", "ENTREGADA"),
            "return": s.status in ("CONFIRMADA", "ENTREGADA"),
        },
    }


@router.get("/{sale_id}/timeline", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sale_timeline(sale_id: int, db: AsyncSession = Depends(get_session)):
    """Devuelve una lista cronológica de eventos de la venta: creación, cambios de estado,
    operaciones de líneas, pagos y devoluciones.
    Formato genérico de evento: {type, at, ...otros campos}.
    """
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    events: list[dict] = []
    # Audit logs relevantes
    q_audit = await db.execute(
        select(AuditLog).where(
            AuditLog.table.in_(["sales", "returns"]), AuditLog.entity_id.isnot(None)
        ).where(
            # Filtrar sólo las acciones vinculadas a esta venta
            or_(
                (AuditLog.table == "sales") & (AuditLog.entity_id == sale_id),
                # returns: meta.sale_id = sale_id
                (AuditLog.table == "returns")
            )
        ).order_by(AuditLog.created_at.asc())
    )
    audit_rows = q_audit.scalars().all()
    # Pre-cargar devoluciones para map meta sale_id
    returns = (await db.execute(select(Return).where(Return.sale_id == sale_id))).scalars().all()
    return_ids = {r.id for r in returns}
    for a in audit_rows:
        meta = a.meta or {}
        if a.table == "returns":
            # incluir sólo returns de esta venta
            sale_id_meta = meta.get("sale_id")
            if sale_id_meta != sale_id and a.entity_id not in return_ids:
                continue
        ev_type = a.action
        ev = {"type": ev_type, "at": a.created_at.isoformat(), "meta": meta}
        events.append(ev)
    # Pagos (si no hay audit individual se incluyen aquí para timeline visual)
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == sale_id).order_by(SalePayment.id.asc()))).scalars().all()
    for p in pays:
        events.append({
            "type": "payment",
            "at": (p.paid_at.isoformat() if p.paid_at else p.created_at.isoformat()),
            "payment_id": p.id,
            "method": p.method,
            "amount": float(p.amount),
            "reference": p.reference,
        })
    # Orden temporal definitivo
    events.sort(key=lambda e: e.get("at"))
    return {"sale_id": sale_id, "events": events, "count": len(events)}


# --- Ventas: listado de pagos (endpoint dedicado) ---
@router.get("/{sale_id}/payments", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_sale_payments(sale_id: int, db: AsyncSession = Depends(get_session)):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == sale_id).order_by(SalePayment.id.asc()))).scalars().all()
    return {
        "sale_id": sale_id,
        "items": [
            {"id": p.id, "method": p.method, "amount": float(p.amount), "reference": p.reference, "paid_at": (p.paid_at.isoformat() if p.paid_at else None)}
            for p in pays
        ],
        "total": len(pays)
    }


# --- Ventas: anulación (revierte stock si estaba confirmada) ---

@router.post("/{sale_id}/annul", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def annul_sale(sale_id: int, reason: str = Query(...), db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        return {"status": s.status, "already": True}
    if s.status not in ("CONFIRMADA", "ENTREGADA"):
        raise HTTPException(status_code=400, detail="Solo se puede anular CONFIRMADA/ENTREGADA")
    # Reponer únicamente el saldo no devuelto de cada línea. La venta queda
    # bloqueada durante el cálculo para serializar anulaciones/devoluciones.
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id).order_by(SaleLine.id))).scalars().all()
    returned_rows = (
        await db.execute(
            select(ReturnLine.sale_line_id, func.coalesce(func.sum(ReturnLine.qty), 0))
            .join(Return, Return.id == ReturnLine.return_id)
            .where(Return.sale_id == s.id)
            .group_by(ReturnLine.sale_line_id)
        )
    ).all()
    returned_by_line = {int(line_id): Decimal(str(total)) for line_id, total in returned_rows}
    product_ids = sorted({line.product_id for line in lines if line.product_id is not None})
    locked_products = (
        await db.execute(
            select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
        )
    ).scalars().all() if product_ids else []
    products = {product.id: product for product in locked_products}
    deltas: list[dict] = []
    for l in lines:
        prod = products.get(l.product_id)
        if not prod:
            continue
        sold_qty = Decimal(str(l.qty or 0))
        returned_qty = returned_by_line.get(l.id, Decimal("0"))
        qty = sold_qty - returned_qty
        if qty < 0:
            raise HTTPException(status_code=409, detail={"code": "return_balance_invalid", "sale_line_id": l.id})
        if qty == 0:
            continue
        before = Decimal(str(prod.stock or 0))
        prod.stock = before + qty
        deltas.append({"product_id": prod.id, "sale_line_id": l.id, "delta": float(qty), "new": float(prod.stock)})
        db.add(StockLedger(
            product_id=prod.id,
            source_type="annul",
            source_id=s.id,
            delta=qty,
            balance_after=prod.stock,
            meta={"sale_line_id": l.id, "sold": float(sold_qty), "returned": float(returned_qty)},
        ))
    s.status = "ANULADA"
    returned_amount = await db.scalar(
        select(func.coalesce(func.sum(Return.total_amount), 0)).where(Return.sale_id == s.id)
    ) or 0
    remaining_credit = max(money(s.total_amount) - money(returned_amount), Decimal("0.00"))
    await add_account_entry(
        db,
        customer_id=s.customer_id,
        entry_type="ANNUL_CREDIT",
        amount=-remaining_credit,
        source_type="annul",
        source_id=s.id,
        user_id=getattr(sess, "user_id", None),
        correlation_id=getattr(sess, "session_id", None),
        note=reason,
    )
    # Audit log con deltas de stock
    _audit(db, "sale_annul", "sales", s.id, {"reason": reason, "stock_deltas": deltas, "returned_amount": float(money(returned_amount)), "credit_amount": float(remaining_credit), "elapsed_ms": 0}, sess, request)
    _report_cache_invalidate()  # anulación afecta métricas agregadas
    await db.commit()
    return {"status": s.status, "restored": deltas}


# --- Ventas: confirmar (valida stock, afecta) y entregar ---

@router.post("/{sale_id}/confirm", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def confirm_sale(sale_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    t0 = time.perf_counter()
    s = await db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    if s.status in ("CONFIRMADA", "ENTREGADA"):
        return {"status": s.status, "already": True}
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    if not lines:
        raise HTTPException(status_code=422, detail="La venta no tiene líneas")
    _recalc_totals(s, lines)
    remaining_discount = money(s.discount_amount)
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            allocated = remaining_discount
        elif Decimal(str(s.subtotal or 0)) > 0:
            allocated = money(Decimal(str(s.discount_amount or 0)) * Decimal(str(line.total or 0)) / Decimal(str(s.subtotal)))
            remaining_discount -= allocated
        else:
            allocated = Decimal("0.00")
        line.global_discount_allocated = allocated
    # Clamp de descuento global si discount_amount excede subtotal
    try:
        from decimal import Decimal as _D
        if s.discount_amount and s.discount_amount > s.subtotal:
            original = float(s.discount_amount)
            s.discount_amount = s.subtotal
            _recalc_totals(s, lines)
            _audit(db, "sale_discount_clamped", "sales", s.id, {
                "original_discount_amount": original,
                "clamped_to": float(s.discount_amount or 0),
                "subtotal": float(s.subtotal or 0)
            }, sess, request)
    except Exception:
        pass
    # Bloqueo por líneas SIN_VINCULAR
    sin_vincular = [l.id for l in lines if (l.state or '').upper() == 'SIN_VINCULAR']
    if sin_vincular:
        raise HTTPException(status_code=409, detail={"code": "lineas_sin_vincular", "lines": sin_vincular})
    await expire_reservations(db, s.id)
    active_reservations = (
        await db.execute(
            select(StockReservation).where(
                StockReservation.sale_id == s.id,
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.utcnow(),
            )
        )
    ).scalars().all()
    reservations_by_line = {row.sale_line_id: row for row in active_reservations}

    quantity_by_product: dict[int, Decimal] = {}
    for line in lines:
        quantity_by_product[line.product_id] = quantity_by_product.get(line.product_id, Decimal("0")) + Decimal(str(line.qty))
    product_ids = sorted(quantity_by_product)
    locked_products = (
        await db.execute(
            select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
        )
    ).scalars().all()
    products = {product.id: product for product in locked_products}
    reserved_rows = (
        await db.execute(
            select(StockReservation.product_id, func.coalesce(func.sum(StockReservation.qty), 0))
            .where(
                StockReservation.product_id.in_(product_ids),
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.utcnow(),
                StockReservation.sale_id != s.id,
            )
            .group_by(StockReservation.product_id)
        )
    ).all()
    reserved_by_product = {product_id: Decimal(str(total)) for product_id, total in reserved_rows}
    missing = []
    for product_id, needed in quantity_by_product.items():
        product = products.get(product_id)
        if not product:
            missing.append({"product_id": product_id, "reason": "no existe"})
            continue
        available = Decimal(str(product.stock or 0)) - reserved_by_product.get(product_id, Decimal("0"))
        if available < needed:
            missing.append({"product_id": product_id, "needed": float(needed), "have": float(available)})
    allow_negative_stock = os.getenv("SALES_ALLOW_NEGATIVE_STOCK", "false").lower() in ("1", "true", "yes")
    if missing and not allow_negative_stock:
        raise HTTPException(status_code=409, detail={"error": "stock_insuficiente", "items": missing})

    credit_customer = await db.get(Customer, s.customer_id) if s.customer_id else None
    if credit_customer and credit_customer.credit_limit is not None:
        current_balance = await account_balance(db, s.customer_id)
        projected = current_balance + money(s.total_amount)
        enforce_limit = os.getenv("SALES_CREDIT_LIMIT_ENFORCED", "true").lower() in ("1", "true", "yes")
        if enforce_limit and projected > Decimal(str(credit_customer.credit_limit)):
            raise HTTPException(
                status_code=409,
                detail={"code": "credit_limit_exceeded", "projected": float(projected)},
            )

    deltas = []
    for l in lines:
        p = products[l.product_id]
        before = Decimal(str(p.stock or 0))
        qty = Decimal(str(l.qty))
        p.stock = before - qty
        if not l.title_snapshot:
            l.title_snapshot = p.title
        if not l.sku_snapshot:
            l.sku_snapshot = p.sku_root
        if l.unit_cost_snapshot is None:
            cost_row = await db.execute(
                select(SupplierProduct.id, SupplierProduct.current_purchase_price)
                .where(
                    SupplierProduct.internal_product_id == p.id,
                    SupplierProduct.current_purchase_price.is_not(None),
                )
                .order_by(SupplierProduct.last_seen_at.desc().nulls_last(), SupplierProduct.id.desc())
                .limit(1)
            )
            cost = cost_row.first()
            if cost:
                l.cost_supplier_product_id = cost[0]
                l.unit_cost_snapshot = cost[1]
        deltas.append({"product_id": p.id, "delta": -float(qty), "new": float(p.stock)})
        db.add(StockLedger(
            product_id=p.id,
            source_type="sale",
            source_id=s.id,
            delta=-qty,
            balance_after=p.stock,
            meta={"sale_line_id": l.id},
        ))
        reservation = reservations_by_line.get(l.id)
        if reservation:
            reservation.status = "CONSUMED"
            reservation.released_at = datetime.utcnow()
    s.status = "CONFIRMADA"
    await add_account_entry(
        db,
        customer_id=s.customer_id,
        entry_type="SALE_CHARGE",
        amount=money(s.total_amount),
        source_type="sale",
        source_id=s.id,
        user_id=getattr(sess, "user_id", None),
        correlation_id=getattr(sess, "session_id", None),
    )
    _audit(db, "sale_confirm", "sales", s.id, {"stock_deltas": deltas, "elapsed_ms": round((time.perf_counter()-t0)*1000,2)}, sess, request)
    _report_cache_invalidate()
    await db.commit()
    return {"status": s.status}

# --- Métricas resumen ventas ---
@router.get("/metrics/summary", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_metrics_summary(db: AsyncSession = Depends(get_session)):
    cache_key = _report_cache_key("metrics_summary")
    cached = _report_cache_get(cache_key)
    if cached:
        return {**cached["data"], "cached": True}
    from datetime import timedelta
    today = datetime.utcnow().date()
    start_today = datetime(today.year, today.month, today.day)
    end_today = start_today + timedelta(days=1)
    q_today = select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_amount), 0)).where(and_(Sale.status.in_(["CONFIRMADA", "ENTREGADA"]), Sale.sale_date >= start_today, Sale.sale_date < end_today))
    row_today = (await db.execute(q_today)).first()
    today_count = int(row_today[0] or 0)
    today_net = float(row_today[1] or 0)
    last7d = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        ds = datetime(d.year, d.month, d.day)
        de = ds + timedelta(days=1)
        qd = select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_amount), 0)).where(and_(Sale.status.in_(["CONFIRMADA", "ENTREGADA"]), Sale.sale_date >= ds, Sale.sale_date < de))
        r = (await db.execute(qd)).first()
        last7d.append({"date": d.isoformat(), "count": int(r[0] or 0), "net_total": float(r[1] or 0)})
    q_top = select(
        SaleLine.product_id,
        func.coalesce(func.sum(SaleLine.qty), 0).label("qty"),
        func.coalesce(func.sum(SaleLine.total), 0).label("total")
    ).join(Sale, SaleLine.sale_id == Sale.id).where(and_(Sale.status.in_(["CONFIRMADA", "ENTREGADA"]), Sale.sale_date >= start_today, Sale.sale_date < end_today)).group_by(SaleLine.product_id).order_by(func.sum(SaleLine.qty).desc()).limit(3)
    top_rows = (await db.execute(q_top)).all()
    prod_titles = {}
    if top_rows:
        ids = [tr.product_id for tr in top_rows if tr.product_id]
        if ids:
            tps = (await db.execute(select(Product.id, Product.title).where(Product.id.in_(ids)))).all()
            prod_titles = {p.id: p.title for p in tps}
    top_products_today = [
        {"product_id": r.product_id, "title": prod_titles.get(r.product_id), "qty": float(r.qty or 0), "total": float(r.total or 0)}
        for r in top_rows
    ]
    # Promedio ms confirm; extraer meta.elapsed_ms adaptando a dialecto (SQLite vs Postgres)
    # Postgres permite meta['elapsed_ms'].astext; SQLite usa json_extract(meta, '$.elapsed_ms')
    from sqlalchemy import literal, text
    avg_ms = 0.0
    try:
        dialect_name = db.bind.dialect.name  # type: ignore
        if dialect_name == 'postgresql':
            # meta -> JSONB en Postgres
            elapsed_expr = cast(AuditLog.meta['elapsed_ms'].astext, Float)  # type: ignore[index]
        else:
            # Asumimos SQLite u otro que soporte json_extract
            elapsed_expr = cast(func.json_extract(AuditLog.meta, '$.elapsed_ms'), Float)
        q_avg = select(func.coalesce(func.avg(elapsed_expr), 0.0)).where(AuditLog.action == 'sale_confirm').order_by(AuditLog.id.desc()).limit(200)
        avg_ms = (await db.execute(q_avg)).scalar() or 0.0
    except Exception:
        avg_ms = 0.0
    result = {
        "today": {"count": today_count, "net_total": today_net},
        "avg_confirm_ms": round(float(avg_ms), 2),
        "last7d": last7d,
        "top_products_today": top_products_today,
    }
    _report_cache_set(cache_key, result, ttl=30)
    return result

@router.get("/reports/net", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_net_report(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (filtra sale_date y created_at de devoluciones)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar por tipo de venta (MOSTRADOR|PEDIDO)"),
    db: AsyncSession = Depends(get_session),
):
    """Reporte agregado de ventas netas.

    Definiciones:
      - bruto: suma de Sale.total_amount de ventas CONFIRMADA/ENTREGADA en rango (sale_date)
      - devoluciones: suma de Return.total_amount de devoluciones cuyo Return.created_at cae en el rango y cuya venta también cumple filtros
      - neto: bruto - devoluciones (no negativo)

    Nota de suposición: el rango se aplica a sale_date para ventas y a created_at para devoluciones (práctica común contable). Si se requiere
    usar sale_date de la venta para filtrar devoluciones en cambio, ajustar lógica futura.
    """
    from datetime import datetime as _dt
    # Cache lookup
    cache_key = _report_cache_key("net", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper())
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    # Parseo de fechas
    from datetime import datetime as _dt_type
    d_from: _dt_type | None = None
    d_to: _dt_type | None = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Base ventas confirmadas / entregadas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)

    sales_subq = select(Sale.id).where(and_(*sales_filter)).subquery()

    gross_stmt = select(func.coalesce(func.sum(Sale.total_amount), 0), func.count(Sale.id)).where(Sale.id.in_(select(sales_subq.c.id)))
    gross_row = await db.execute(gross_stmt)
    gross_amount, gross_count = gross_row.first() or (0,0)

    # Devoluciones ligadas a esas ventas (Return.sale_id IN sales_subq) y created_at dentro del rango
    returns_filter = [Return.sale_id.in_(select(sales_subq.c.id))]
    if d_from:
        returns_filter.append(Return.created_at >= d_from)
    if d_to:
        returns_filter.append(Return.created_at <= d_to)
    returns_stmt = select(func.coalesce(func.sum(Return.total_amount), 0), func.count(Return.id)).where(and_(*returns_filter))
    ret_row = await db.execute(returns_stmt)
    returns_amount, returns_count = ret_row.first() or (0,0)

    from decimal import Decimal as _D
    bruto = _D(str(gross_amount or 0))
    devol = _D(str(returns_amount or 0))
    neto = bruto - devol
    if neto < 0:
        neto = _D("0")

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None},
        "bruto": float(bruto),
        "devoluciones": float(devol),
        "neto": float(neto),
        "ventas": int(gross_count or 0),
        "devoluciones_count": int(returns_count or 0),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result


@router.get("/reports/top-products", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_top_products(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (sale_date)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar tipo venta"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de productos"),
    db: AsyncSession = Depends(get_session),
):
    """Ranking de productos por cantidad vendida y monto neto (considerando descuentos de línea).

    Cálculo:
      - Se consideran ventas en estado CONFIRMADA o ENTREGADA.
      - Monto línea: unit_price * qty * (1 - line_discount%).
      - Se descuenta (resta) la cantidad y subtotal de devoluciones registradas dentro del rango (Return.created_at).
      - Rango aplica sobre Sale.sale_date para ventas y Return.created_at para devoluciones.

    Nota: No se prorratea descuento global de la venta a las líneas; este cálculo usa sólo descuento de línea. Refinamiento futuro podría
    distribuir discount_amount global proporcionalmente.
    """
    from datetime import datetime as _dt
    cache_key = _report_cache_key("top_products", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper(), limit=limit)
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    from decimal import Decimal as _D
    # Parse fechas
    d_from = d_to = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Subquery ventas filtradas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)
    sales_subq = select(Sale.id).where(and_(*sales_filter)).subquery()

    # Agregación líneas de venta
    line_stmt = select(
        SaleLine.product_id.label("product_id"),
        func.coalesce(func.sum(SaleLine.qty), 0).label("qty_total"),
        func.coalesce(func.sum( (SaleLine.unit_price * SaleLine.qty) * (1 - (SaleLine.line_discount/100)) ), 0).label("amount_total"),
    ).where(SaleLine.sale_id.in_(select(sales_subq.c.id))).group_by(SaleLine.product_id)
    line_rows = (await db.execute(line_stmt)).all()
    agg_map: dict[int, dict] = {}
    for r in line_rows:
        pid = int(r.product_id)
        agg_map[pid] = {
            "product_id": pid,
            "qty": float(r.qty_total or 0),
            "amount": float(r.amount_total or 0),
            "returns_qty": 0.0,
            "returns_amount": 0.0,
        }

    # Devoluciones dentro de rango (Return.created_at)
    returns_filter = [Return.sale_id.in_(select(sales_subq.c.id))]
    if d_from:
        returns_filter.append(Return.created_at >= d_from)
    if d_to:
        returns_filter.append(Return.created_at <= d_to)
    # join ReturnLine -> Return para filtrar
    from sqlalchemy import join as _join
    rl = ReturnLine
    r = Return
    ret_stmt = select(
        rl.product_id,
        func.coalesce(func.sum(rl.qty), 0).label("r_qty"),
        func.coalesce(func.sum(rl.subtotal), 0).label("r_amount"),
    ).select_from(_join(rl, r, rl.return_id == r.id)).where(and_(*returns_filter)).group_by(rl.product_id)
    ret_rows = (await db.execute(ret_stmt)).all()
    for rr in ret_rows:
        pid = int(rr.product_id)
        if pid not in agg_map:
            # Caso: devolución de producto cuya venta está filtrada pero sin líneas (raro); se registra negativo
            agg_map[pid] = {"product_id": pid, "qty": 0.0, "amount": 0.0, "returns_qty": 0.0, "returns_amount": 0.0}
        agg_map[pid]["returns_qty"] = float(rr.r_qty or 0)
        agg_map[pid]["returns_amount"] = float(rr.r_amount or 0)

    # Construir ranking neto
    rows = []
    for pid, data in agg_map.items():
        net_qty = data["qty"] - data["returns_qty"]
        net_amount = data["amount"] - data["returns_amount"]
        if net_qty < 0:
            net_qty = 0.0
        if net_amount < 0:
            net_amount = 0.0
        rows.append({
            "product_id": pid,
            "qty_vendida": round(data["qty"], 2),
            "qty_devuelta": round(data["returns_qty"], 2),
            "qty_neta": round(net_qty, 2),
            "monto_vendido": round(data["amount"], 2),
            "monto_devuelto": round(data["returns_amount"], 2),
            "monto_neto": round(net_amount, 2),
        })
    # Orden principal por monto_neto desc luego qty_neta desc
    rows.sort(key=lambda x: (x["monto_neto"], x["qty_neta"]), reverse=True)
    rows = rows[:limit]

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None, "limit": limit},
        "items": rows,
        "count": len(rows),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result



@router.post("/{sale_id}/deliver", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def deliver_sale(sale_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.get(Sale, sale_id)
    t0 = time.perf_counter()
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    if s.status == "ENTREGADA":
        return {"status": s.status, "already": True}
    # Permitir entregar si está CONFIRMADA (o entregada ya)
    if s.status != "CONFIRMADA":
        raise HTTPException(status_code=400, detail="Solo se puede ENTREGAR si está CONFIRMADA")
    s.status = "ENTREGADA"
    _audit(db, "sale_deliver", "sales", s.id, {"elapsed_ms": round((time.perf_counter()-t0)*1000,2)}, sess, request)
    await db.commit()
    return {"status": s.status}


# --- Ventas: pagos adicionales y recibo ---

@router.post("/{sale_id}/payments", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def add_payment(sale_id: int, payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    method = _normalize_payment_method(payload.get("method"))
    amount = Decimal(str(payload.get("amount") or 0))
    reference = payload.get("reference") or None
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount debe ser > 0")
    prev_paid = Decimal(str(s.paid_total or 0))
    prev_status = s.payment_status
    # Regla: permitir pagos adicionales mientras la venta no esté ANULADA
    # y el total abonado no exceda (total_amount + margen tolerancia opcional).
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    # Evitar sobrepago significativo: permitir pequeño redondeo (2 centavos) por temas de Decimal
    total_amount = Decimal(str(s.total_amount or 0))
    if total_amount is not None and total_amount > 0:
        if prev_paid >= total_amount and amount > 0:
            # Ya estaba saldada
            raise HTTPException(status_code=400, detail="Venta ya saldada")
        if prev_paid + amount > (total_amount + Decimal("0.02")):
            raise HTTPException(status_code=409, detail={"code": "sobrepago", "message": "El pago excede el total"})
    p = SalePayment(sale_id=s.id, method=method, amount=amount, reference=reference)
    db.add(p)
    await db.flush()  # obtener p.id
    await add_account_entry(
        db,
        customer_id=s.customer_id,
        entry_type="PAYMENT",
        amount=-money(amount),
        source_type="payment",
        source_id=p.id,
        user_id=getattr(sess, "user_id", None),
        correlation_id=getattr(sess, "session_id", None),
        note=reference,
    )
    total_paid = prev_paid + amount
    s.paid_total = total_paid
    if total_paid == 0:
        s.payment_status = "PENDIENTE"
    elif total_paid < (s.total_amount or Decimal("0")):
        s.payment_status = "PARCIAL"
    else:
        s.payment_status = "PAGADA"
    await db.flush()
    _audit(db, "sale_payment_add", "sales", s.id, {
        "payment_id": p.id,
        "method": method,
        "amount": float(amount),
        "reference": reference,
        "before": {"paid_total": float(prev_paid), "payment_status": prev_status},
        "after": {"paid_total": float(s.paid_total or 0), "payment_status": s.payment_status},
    }, sess, request)
    await db.commit()
    return {"payment_id": p.id, "paid_total": float(s.paid_total or 0), "payment_status": s.payment_status}


@router.get("/reports/top-customers", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_top_customers(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (sale_date)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar tipo venta"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de clientes"),
    db: AsyncSession = Depends(get_session),
):
    """Ranking de clientes por monto bruto y neto (descontando devoluciones), y cantidad de operaciones.

    Definiciones:
      - monto_bruto: suma de Sale.total_amount de ventas CONFIRMADA/ENTREGADA para el cliente.
      - monto_devoluciones: suma de Return.total_amount asociado a esas ventas (Return.created_at en rango).
      - monto_neto: max(monto_bruto - monto_devoluciones, 0).
      - ventas_count: cantidad de ventas involucradas.
      - devoluciones_count: cantidad de devoluciones.
    """
    from datetime import datetime as _dt
    cache_key = _report_cache_key("top_customers", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper(), limit=limit)
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    # Parse fechas
    d_from = d_to = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Ventas filtradas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)
    sales_subq = select(Sale.id, Sale.customer_id, Sale.total_amount).where(and_(*sales_filter)).subquery()

    # Agregación ventas por cliente
    sales_agg_stmt = select(
        sales_subq.c.customer_id.label("customer_id"),
        func.coalesce(func.sum(sales_subq.c.total_amount), 0).label("monto_bruto"),
        func.count(sales_subq.c.id).label("ventas_count"),
    ).group_by(sales_subq.c.customer_id)
    sales_rows = (await db.execute(sales_agg_stmt)).all()
    agg_map: dict[int | None, dict] = {}
    for r in sales_rows:
        cid = r.customer_id if r.customer_id is not None else 0  # usar 0 para clientes nulos (Consumidor Final)
        agg_map[cid] = {
            "customer_id": r.customer_id,
            "monto_bruto": float(r.monto_bruto or 0),
            "ventas_count": int(r.ventas_count or 0),
            "monto_devoluciones": 0.0,
            "devoluciones_count": 0,
        }

    # Construir ranking
    rows = []
    for cid, data in agg_map.items():
        neto = data["monto_bruto"] - data["monto_devoluciones"]
        if neto < 0:
            neto = 0.0
        rows.append({
            "customer_id": data["customer_id"],
            "monto_bruto": round(data["monto_bruto"], 2),
            "monto_devoluciones": round(data["monto_devoluciones"], 2),
            "monto_neto": round(neto, 2),
            "ventas_count": data["ventas_count"],
            "devoluciones_count": data["devoluciones_count"],
        })
    rows.sort(key=lambda x: (x["monto_neto"], x["monto_bruto"]), reverse=True)
    rows = rows[:limit]

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None, "limit": limit},
        "items": rows,
        "count": len(rows),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result


# --- Clientes: búsqueda rápida ---


@router.get("/{sale_id}/receipt", response_class=HTMLResponse, dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_receipt(sale_id: int, db: AsyncSession = Depends(get_session)):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == s.id))).scalars().all()
    total = float(s.total_amount or 0)
    html = [
        "<html><head><meta charset='utf-8'><title>Recibo</title>",
        "<style>body{font-family:Arial,sans-serif;margin:20px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ccc;padding:6px}</style>",
        "</head><body>",
        f"<h2>Recibo de Venta #{s.id}</h2>",
        f"<div>Fecha: {s.sale_date.strftime('%Y-%m-%d %H:%M')}</div>",
        f"<div>Cliente: {s.customer_id or '-'} · Estado: {s.status}</div>",
        "<h3>Ítems</h3>",
        "<table><thead><tr><th>Producto</th><th>Cant</th><th>P.unit</th><th>Desc%</th><th>Total</th></tr></thead><tbody>",
    ]
    for l in lines:
        html.append(f"<tr><td>{l.product_id}</td><td>{float(l.qty):.0f}</td><td>${float(l.unit_price):.2f}</td><td>{float(l.line_discount or 0):.2f}%</td><td>${float(l.unit_price)*float(l.qty)*(1-float(l.line_discount or 0)/100):.2f}</td></tr>")
    html.append("</tbody></table>")
    html.append(f"<h3>Total: ${total:.2f}</h3>")
    if pays:
        html.append("<h4>Pagos</h4><ul>")
        for p in pays:
            html.append(f"<li>{p.method}: ${float(p.amount):.2f} {p.reference or ''}</li>")
        html.append("</ul>")
    html.append("</body></html>")
    return "".join(html)


@router.post("/{sale_id}/attachments", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def upload_sale_attachment(sale_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    declared_mime = (file.content_type or "").lower()
    extension_by_mime = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    suffix = Path(file.filename or "").suffix.lower()
    if declared_mime not in allowed or (declared_mime == "image/jpeg" and suffix not in {".jpg", ".jpeg"}) or (declared_mime != "image/jpeg" and suffix != extension_by_mime.get(declared_mime)):
        raise HTTPException(status_code=415, detail="Tipo de adjunto no permitido")
    max_bytes = max(1, int(os.getenv("SALES_ATTACHMENTS_MAX_MB", "10"))) * 1024 * 1024
    if getattr(file, "size", None) is not None and file.size > max_bytes:
        raise HTTPException(status_code=413, detail="El adjunto supera el tamaño máximo")
    count = await db.scalar(select(func.count(SaleAttachment.id)).where(SaleAttachment.sale_id == sale_id)) or 0
    if count >= 5:
        raise HTTPException(status_code=409, detail="La venta ya tiene el máximo de cinco adjuntos")
    path, sha256 = await save_upload("sales", file.filename, file)
    signature = path.read_bytes()[:16]
    detected_mime = (
        "application/pdf" if signature.startswith(b"%PDF-") else
        "image/jpeg" if signature.startswith(b"\xff\xd8\xff") else
        "image/png" if signature.startswith(b"\x89PNG\r\n\x1a\n") else
        "image/webp" if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP" else None
    )
    if detected_mime != declared_mime:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail="El contenido real no coincide con el tipo de archivo")
    if path.stat().st_size > max_bytes:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="El adjunto supera el tamaño máximo")
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


@router.get("/{sale_id}/attachments", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_sale_attachments(sale_id: int, db: AsyncSession = Depends(get_session)):
    if not await db.get(Sale, sale_id):
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    rows = (
        await db.execute(
            select(SaleAttachment).where(SaleAttachment.sale_id == sale_id).order_by(SaleAttachment.id)
        )
    ).scalars().all()
    return {
        "items": [
            {"id": row.id, "filename": row.filename, "mime": row.mime, "size": row.size, "path": row.path}
            for row in rows
        ]
    }


@router.delete("/{sale_id}/attachments/{attachment_id}", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def delete_sale_attachment(sale_id: int, attachment_id: int, db: AsyncSession = Depends(get_session)):
    attachment = await db.get(SaleAttachment, attachment_id)
    if not attachment or attachment.sale_id != sale_id:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    path = get_media_root() / attachment.path
    if path.is_file():
        path.unlink(missing_ok=True)
    await db.delete(attachment)
    await db.commit()
    return {"status": "deleted", "id": attachment_id}


# --- Devoluciones (Returns) ---

@router.post("/{sale_id}/returns", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def create_return(sale_id: int, payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    """Registra una devolución parcial o total de una venta CONFIRMADA/ENTREGADA.

    payload:
      - reason (opcional)
      - items: lista de { sale_line_id: int, qty: number }
    Validaciones:
      - Venta debe estar CONFIRMADA o ENTREGADA
      - qty > 0 y no excede saldo (vendido - devuelto previo) de la línea
    Efectos:
      - Incrementa stock de productos devueltos
      - Guarda Return + ReturnLines + AuditLog return_create
    """
    t0 = time.perf_counter()
    sale = await db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if sale.status not in ("CONFIRMADA", "ENTREGADA"):
        raise HTTPException(status_code=400, detail="Sólo se permiten devoluciones de ventas CONFIRMADA/ENTREGADA")
    if sale.status == "ANULADA":  # por si cambia flujo futuro
        raise HTTPException(status_code=400, detail="Venta anulada")
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="items requerido")
    reason = (payload.get("reason") or None)

    # Pre-cargar líneas de venta involucradas
    line_ids = [int(it.get("sale_line_id")) for it in items if it.get("sale_line_id") is not None]
    if not line_ids:
        raise HTTPException(status_code=400, detail="Cada item debe incluir sale_line_id")
    q_lines = (
        await db.execute(
            select(SaleLine).where(SaleLine.id.in_(line_ids)).order_by(SaleLine.id).with_for_update()
        )
    ).scalars().all()
    lines_map = {l.id: l for l in q_lines if l.sale_id == sale.id}
    if len(lines_map) != len(line_ids):
        raise HTTPException(status_code=400, detail="Alguna sale_line no pertenece a la venta")

    # Calcular ya devuelto por línea
    # SELECT sale_line_id, COALESCE(SUM(qty),0) FROM return_lines rl JOIN returns r ON rl.return_id=r.id WHERE r.sale_id=:sale_id GROUP BY sale_line_id
    returned_map: dict[int, Decimal] = {}
    from sqlalchemy import join
    rl_alias = ReturnLine
    r_alias = Return
    rows = (await db.execute(
        select(rl_alias.sale_line_id, func.coalesce(func.sum(rl_alias.qty), 0)).select_from(
            join(rl_alias, r_alias, rl_alias.return_id == r_alias.id)
        ).where(r_alias.sale_id == sale_id).group_by(rl_alias.sale_line_id)
    )).all()
    for sl_id, qty_sum in rows:
        if sl_id is not None:
            returned_map[int(sl_id)] = Decimal(str(qty_sum))

    ret = Return(sale_id=sale.id, status="REGISTRADA", reason=reason, created_by=getattr(sess, "user_id", None), correlation_id=getattr(sess, "session_id", None))
    db.add(ret)
    await db.flush()

    product_ids = sorted({line.product_id for line in lines_map.values() if line.product_id is not None})
    locked_products = (
        await db.execute(
            select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
        )
    ).scalars().all() if product_ids else []
    products = {product.id: product for product in locked_products}

    total_amount = Decimal("0")
    stock_deltas: list[dict] = []
    for it in items:
        sl_id = int(it.get("sale_line_id"))
        line = lines_map[sl_id]
        qty_req = quantity(it.get("qty"))
        prev_ret = returned_map.get(sl_id, Decimal("0"))
        saldo = Decimal(str(line.qty)) - prev_ret
        if qty_req > saldo:
            raise HTTPException(status_code=400, detail=f"qty excede saldo disponible (vendido {line.qty} ya devuelto {prev_ret}) en línea {sl_id}")
        line_total_unit = Decimal(str(line.unit_price)) * qty_req * (Decimal("1") - Decimal(str(line.line_discount or 0))/Decimal("100"))
        total_amount += line_total_unit
        rl = ReturnLine(
            return_id=ret.id,
            sale_line_id=sl_id,
            product_id=line.product_id,
            qty=qty_req,
            unit_price=line.unit_price,
            subtotal=line_total_unit,
        )
        db.add(rl)
        # Incrementar stock
        prod = products.get(line.product_id)
        if prod:
            before = Decimal(str(prod.stock or 0))
            prod.stock = before + qty_req
            stock_deltas.append({"product_id": prod.id, "delta": float(qty_req), "new": float(prod.stock)})
            db.add(StockLedger(
                product_id=prod.id,
                source_type="return",
                source_id=ret.id,
                delta=qty_req,
                balance_after=prod.stock,
                meta={"sale_line_id": sl_id},
            ))

    ret.total_amount = total_amount
    await add_account_entry(
        db,
        customer_id=sale.customer_id,
        entry_type="RETURN_CREDIT",
        amount=-money(total_amount),
        source_type="return",
        source_id=ret.id,
        user_id=getattr(sess, "user_id", None),
        correlation_id=getattr(sess, "session_id", None),
        note=reason,
    )
    _audit(db, "return_create", "returns", ret.id, {
        "sale_id": sale.id,
        "lines": len(items),
        "total": float(total_amount),
        "stock_deltas": stock_deltas,
        "elapsed_ms": round((time.perf_counter()-t0)*1000,2),
    }, sess, request)
    # Invalidate report cache (devoluciones afectan reportes)
    _report_cache_invalidate()
    await db.commit()
    return {"return_id": ret.id, "total": float(total_amount), "lines": len(items)}


@router.get("/{sale_id}/returns", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def list_returns(sale_id: int, db: AsyncSession = Depends(get_session)):
    sale = await db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    rets = (await db.execute(select(Return).where(Return.sale_id == sale_id).order_by(Return.id.asc()))).scalars().all()
    result = []
    for r in rets:
        lines = (await db.execute(select(ReturnLine).where(ReturnLine.return_id == r.id))).scalars().all()
        result.append({
            "id": r.id,
            "status": r.status,
            "reason": r.reason,
            "total": float(r.total_amount or 0),
            "created_at": r.created_at.isoformat(),
            "lines": [
                {"id": l.id, "sale_line_id": l.sale_line_id, "product_id": l.product_id, "qty": float(l.qty), "unit_price": float(l.unit_price), "subtotal": float(l.subtotal or 0)} for l in lines
            ]
        })
    return {"items": result, "total": len(result)}


# --- Reportes ventas (neto) ---

@router.get("/reports/net", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_net_report(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (filtra sale_date y created_at de devoluciones)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar por tipo de venta (MOSTRADOR|PEDIDO)"),
    db: AsyncSession = Depends(get_session),
):
    """Reporte agregado de ventas netas.

    Definiciones:
      - bruto: suma de Sale.total_amount de ventas CONFIRMADA/ENTREGADA en rango (sale_date)
      - devoluciones: suma de Return.total_amount de devoluciones cuyo Return.created_at cae en el rango y cuya venta también cumple filtros
      - neto: bruto - devoluciones (no negativo)

    Nota de suposición: el rango se aplica a sale_date para ventas y a created_at para devoluciones (práctica común contable). Si se requiere
    usar sale_date de la venta para filtrar devoluciones en cambio, ajustar lógica futura.
    """
    from datetime import datetime as _dt
    # Cache lookup
    cache_key = _report_cache_key("net", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper())
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    # Parseo de fechas
    from datetime import datetime as _dt_type
    d_from: _dt_type | None = None
    d_to: _dt_type | None = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Base ventas confirmadas / entregadas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)

    sales_subq = select(Sale.id).where(and_(*sales_filter)).subquery()

    gross_stmt = select(func.coalesce(func.sum(Sale.total_amount), 0), func.count(Sale.id)).where(Sale.id.in_(select(sales_subq.c.id)))
    gross_row = await db.execute(gross_stmt)
    gross_amount, gross_count = gross_row.first() or (0,0)

    # Devoluciones ligadas a esas ventas (Return.sale_id IN sales_subq) y created_at dentro del rango
    returns_filter = [Return.sale_id.in_(select(sales_subq.c.id))]
    if d_from:
        returns_filter.append(Return.created_at >= d_from)
    if d_to:
        returns_filter.append(Return.created_at <= d_to)
    returns_stmt = select(func.coalesce(func.sum(Return.total_amount), 0), func.count(Return.id)).where(and_(*returns_filter))
    ret_row = await db.execute(returns_stmt)
    returns_amount, returns_count = ret_row.first() or (0,0)

    from decimal import Decimal as _D
    bruto = _D(str(gross_amount or 0))
    devol = _D(str(returns_amount or 0))
    neto = bruto - devol
    if neto < 0:
        neto = _D("0")

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None},
        "bruto": float(bruto),
        "devoluciones": float(devol),
        "neto": float(neto),
        "ventas": int(gross_count or 0),
        "devoluciones_count": int(returns_count or 0),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result


@router.get("/reports/top-products", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_top_products(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (sale_date)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar tipo venta"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de productos"),
    db: AsyncSession = Depends(get_session),
):
    """Ranking de productos por cantidad vendida y monto neto (considerando descuentos de línea).

    Cálculo:
      - Se consideran ventas en estado CONFIRMADA o ENTREGADA.
      - Monto línea: unit_price * qty * (1 - line_discount%).
      - Se descuenta (resta) la cantidad y subtotal de devoluciones registradas dentro del rango (Return.created_at).
      - Rango aplica sobre Sale.sale_date para ventas y Return.created_at para devoluciones.

    Nota: No se prorratea descuento global de la venta a las líneas; este cálculo usa sólo descuento de línea. Refinamiento futuro podría
    distribuir discount_amount global proporcionalmente.
    """
    from datetime import datetime as _dt
    cache_key = _report_cache_key("top_products", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper(), limit=limit)
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    from decimal import Decimal as _D
    # Parse fechas
    d_from = d_to = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Subquery ventas filtradas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)
    sales_subq = select(Sale.id).where(and_(*sales_filter)).subquery()

    # Agregación líneas de venta
    line_stmt = select(
        SaleLine.product_id.label("product_id"),
        func.coalesce(func.sum(SaleLine.qty), 0).label("qty_total"),
        func.coalesce(func.sum( (SaleLine.unit_price * SaleLine.qty) * (1 - (SaleLine.line_discount/100)) ), 0).label("amount_total"),
    ).where(SaleLine.sale_id.in_(select(sales_subq.c.id))).group_by(SaleLine.product_id)
    line_rows = (await db.execute(line_stmt)).all()
    agg_map: dict[int, dict] = {}
    for r in line_rows:
        pid = int(r.product_id)
        agg_map[pid] = {
            "product_id": pid,
            "qty": float(r.qty_total or 0),
            "amount": float(r.amount_total or 0),
            "returns_qty": 0.0,
            "returns_amount": 0.0,
        }

    # Devoluciones dentro de rango (Return.created_at)
    returns_filter = [Return.sale_id.in_(select(sales_subq.c.id))]
    if d_from:
        returns_filter.append(Return.created_at >= d_from)
    if d_to:
        returns_filter.append(Return.created_at <= d_to)
    # join ReturnLine -> Return para filtrar
    from sqlalchemy import join as _join
    rl = ReturnLine
    r = Return
    ret_stmt = select(
        rl.product_id,
        func.coalesce(func.sum(rl.qty), 0).label("r_qty"),
        func.coalesce(func.sum(rl.subtotal), 0).label("r_amount"),
    ).select_from(_join(rl, r, rl.return_id == r.id)).where(and_(*returns_filter)).group_by(rl.product_id)
    ret_rows = (await db.execute(ret_stmt)).all()
    for rr in ret_rows:
        pid = int(rr.product_id)
        if pid not in agg_map:
            # Caso: devolución de producto cuya venta está filtrada pero sin líneas (raro); se registra negativo
            agg_map[pid] = {"product_id": pid, "qty": 0.0, "amount": 0.0, "returns_qty": 0.0, "returns_amount": 0.0}
        agg_map[pid]["returns_qty"] = float(rr.r_qty or 0)
        agg_map[pid]["returns_amount"] = float(rr.r_amount or 0)

    # Construir ranking neto
    rows = []
    for pid, data in agg_map.items():
        net_qty = data["qty"] - data["returns_qty"]
        net_amount = data["amount"] - data["returns_amount"]
        if net_qty < 0:
            net_qty = 0.0
        if net_amount < 0:
            net_amount = 0.0
        rows.append({
            "product_id": pid,
            "qty_vendida": round(data["qty"], 2),
            "qty_devuelta": round(data["returns_qty"], 2),
            "qty_neta": round(net_qty, 2),
            "monto_vendido": round(data["amount"], 2),
            "monto_devuelto": round(data["returns_amount"], 2),
            "monto_neto": round(net_amount, 2),
        })
    # Orden principal por monto_neto desc luego qty_neta desc
    rows.sort(key=lambda x: (x["monto_neto"], x["qty_neta"]), reverse=True)
    rows = rows[:limit]

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None, "limit": limit},
        "items": rows,
        "count": len(rows),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result



@router.post("/{sale_id}/deliver", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def deliver_sale(sale_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.get(Sale, sale_id)
    t0 = time.perf_counter()
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    if s.status == "ENTREGADA":
        return {"status": s.status, "already": True}
    # Permitir entregar si está CONFIRMADA (o entregada ya)
    if s.status != "CONFIRMADA":
        raise HTTPException(status_code=400, detail="Solo se puede ENTREGAR si está CONFIRMADA")
    s.status = "ENTREGADA"
    _audit(db, "sale_deliver", "sales", s.id, {"elapsed_ms": round((time.perf_counter()-t0)*1000,2)}, sess, request)
    await db.commit()
    return {"status": s.status}


# --- Ventas: pagos adicionales y recibo ---

@router.post("/{sale_id}/payments", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def add_payment(sale_id: int, payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    method = _normalize_payment_method(payload.get("method"))
    amount = Decimal(str(payload.get("amount") or 0))
    reference = payload.get("reference") or None
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount debe ser > 0")
    prev_paid = Decimal(str(s.paid_total or 0))
    prev_status = s.payment_status
    # Regla: permitir pagos adicionales mientras la venta no esté ANULADA
    # y el total abonado no exceda (total_amount + margen tolerancia opcional).
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    # Evitar sobrepago significativo: permitir pequeño redondeo (2 centavos) por temas de Decimal
    total_amount = Decimal(str(s.total_amount or 0))
    if total_amount is not None and total_amount > 0:
        if prev_paid >= total_amount and amount > 0:
            # Ya estaba saldada
            raise HTTPException(status_code=400, detail="Venta ya saldada")
        if prev_paid + amount > (total_amount + Decimal("0.02")):
            raise HTTPException(status_code=409, detail={"code": "sobrepago", "message": "El pago excede el total"})
    p = SalePayment(sale_id=s.id, method=method, amount=amount, reference=reference)
    db.add(p)
    await db.flush()  # obtener p.id
    total_paid = prev_paid + amount
    s.paid_total = total_paid
    if total_paid == 0:
        s.payment_status = "PENDIENTE"
    elif total_paid < (s.total_amount or Decimal("0")):
        s.payment_status = "PARCIAL"
    else:
        s.payment_status = "PAGADA"
    await db.flush()
    _audit(db, "sale_payment_add", "sales", s.id, {
        "payment_id": p.id,
        "method": method,
        "amount": float(amount),
        "reference": reference,
        "before": {"paid_total": float(prev_paid), "payment_status": prev_status},
        "after": {"paid_total": float(s.paid_total or 0), "payment_status": s.payment_status},
    }, sess, request)
    await db.commit()
    return {"payment_id": p.id, "paid_total": float(s.paid_total or 0), "payment_status": s.payment_status}


@router.get("/reports/top-customers", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_top_customers(
    dt_from: Optional[str] = Query(None, description="Fecha/hora ISO inicio (sale_date)"),
    dt_to: Optional[str] = Query(None, description="Fecha/hora ISO fin (inclusive)"),
    sale_kind: Optional[str] = Query(None, description="Filtrar tipo venta"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de clientes"),
    db: AsyncSession = Depends(get_session),
):
    """Ranking de clientes por monto bruto y neto (descontando devoluciones), y cantidad de operaciones.

    Definiciones:
      - monto_bruto: suma de Sale.total_amount de ventas CONFIRMADA/ENTREGADA para el cliente.
      - monto_devoluciones: suma de Return.total_amount asociado a esas ventas (Return.created_at en rango).
      - monto_neto: max(monto_bruto - monto_devoluciones, 0).
      - ventas_count: cantidad de ventas involucradas.
      - devoluciones_count: cantidad de devoluciones.
    """
    from datetime import datetime as _dt
    cache_key = _report_cache_key("top_customers", dt_from=dt_from or "", dt_to=dt_to or "", sale_kind=(sale_kind or "").upper(), limit=limit)
    cached = _report_cache_get(cache_key)
    if cached:
        return cached
    # Parse fechas
    d_from = d_to = None
    if dt_from:
        try:
            d_from = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_from formato inválido")
    if dt_to:
        try:
            d_to = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="dt_to formato inválido")

    # Ventas filtradas
    sales_filter = [Sale.status.in_(["CONFIRMADA", "ENTREGADA"]) ]
    if sale_kind:
        sales_filter.append(Sale.sale_kind == sale_kind.upper())
    if d_from:
        sales_filter.append(Sale.sale_date >= d_from)
    if d_to:
        sales_filter.append(Sale.sale_date <= d_to)
    sales_subq = select(Sale.id, Sale.customer_id, Sale.total_amount).where(and_(*sales_filter)).subquery()

    # Agregación ventas por cliente
    sales_agg_stmt = select(
        sales_subq.c.customer_id.label("customer_id"),
        func.coalesce(func.sum(sales_subq.c.total_amount), 0).label("monto_bruto"),
        func.count(sales_subq.c.id).label("ventas_count"),
    ).group_by(sales_subq.c.customer_id)
    sales_rows = (await db.execute(sales_agg_stmt)).all()
    agg_map: dict[int | None, dict] = {}
    for r in sales_rows:
        cid = r.customer_id if r.customer_id is not None else 0  # usar 0 para clientes nulos (Consumidor Final)
        agg_map[cid] = {
            "customer_id": r.customer_id,
            "monto_bruto": float(r.monto_bruto or 0),
            "ventas_count": int(r.ventas_count or 0),
            "monto_devoluciones": 0.0,
            "devoluciones_count": 0,
        }

    # Devoluciones filtradas (Return.created_at) asociadas a esas ventas
    returns_filter = [Return.sale_id.in_(select(sales_subq.c.id))]
    if d_from:
        returns_filter.append(Return.created_at >= d_from)
    if d_to:
        returns_filter.append(Return.created_at <= d_to)
    # join Return -> Sale para traer customer_id
    from sqlalchemy import join as _join
    r = Return
    s = Sale
    ret_stmt = select(
        s.customer_id.label("customer_id"),
        func.coalesce(func.sum(r.total_amount), 0).label("monto_dev"),
        func.count(r.id).label("ret_count"),
    ).select_from(_join(r, s, r.sale_id == s.id)).where(and_(*returns_filter)).group_by(s.customer_id)
    ret_rows = (await db.execute(ret_stmt)).all()
    for rr in ret_rows:
        cid = rr.customer_id if rr.customer_id is not None else 0
        if cid not in agg_map:
            agg_map[cid] = {
                "customer_id": rr.customer_id,
                "monto_bruto": 0.0,
                "ventas_count": 0,
                "monto_devoluciones": 0.0,
                "devoluciones_count": 0,
            }
        agg_map[cid]["monto_devoluciones"] = float(rr.monto_dev or 0)
        agg_map[cid]["devoluciones_count"] = int(rr.ret_count or 0)

    # Construir ranking
    rows = []
    for cid, data in agg_map.items():
        neto = data["monto_bruto"] - data["monto_devoluciones"]
        if neto < 0:
            neto = 0.0
        rows.append({
            "customer_id": data["customer_id"],
            "monto_bruto": round(data["monto_bruto"], 2),
            "monto_devoluciones": round(data["monto_devoluciones"], 2),
            "monto_neto": round(neto, 2),
            "ventas_count": data["ventas_count"],
            "devoluciones_count": data["devoluciones_count"],
        })
    rows.sort(key=lambda x: (x["monto_neto"], x["monto_bruto"]), reverse=True)
    rows = rows[:limit]

    result = {
        "filters": {"dt_from": dt_from, "dt_to": dt_to, "sale_kind": sale_kind.upper() if sale_kind else None, "limit": limit},
        "items": rows,
        "count": len(rows),
        "cached": False,
    }
    _report_cache_set(cache_key, {**result, "cached": True})
    return result


# --- Clientes: búsqueda rápida ---


@router.get("/{sale_id}/receipt", response_class=HTMLResponse, dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_receipt(sale_id: int, db: AsyncSession = Depends(get_session)):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == s.id))).scalars().all()
    total = float(s.total_amount or 0)
    html = [
        "<html><head><meta charset='utf-8'><title>Recibo</title>",
        "<style>body{font-family:Arial,sans-serif;margin:20px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ccc;padding:6px}</style>",
        "</head><body>",
        f"<h2>Recibo de Venta #{s.id}</h2>",
        f"<div>Fecha: {s.sale_date.strftime('%Y-%m-%d %H:%M')}</div>",
        f"<div>Cliente: {s.customer_id or '-'} · Estado: {s.status}</div>",
        "<h3>Ítems</h3>",
        "<table><thead><tr><th>Producto</th><th>Cant</th><th>P.unit</th><th>Desc%</th><th>Total</th></tr></thead><tbody>",
    ]
    for l in lines:
        html.append(f"<tr><td>{l.product_id}</td><td>{float(l.qty):.0f}</td><td>${float(l.unit_price):.2f}</td><td>{float(l.line_discount or 0):.2f}%</td><td>${float(l.unit_price)*float(l.qty)*(1-float(l.line_discount or 0)/100):.2f}</td></tr>")
    html.append("</tbody></table>")
    html.append(f"<h3>Total: ${total:.2f}</h3>")
    if pays:
        html.append("<h4>Pagos</h4><ul>")
        for p in pays:
            html.append(f"<li>{p.method}: ${float(p.amount):.2f} {p.reference or ''}</li>")
        html.append("</ul>")
    html.append("</body></html>")
    return "".join(html)


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


# --- Export CSV ventas ---

@router.get("/export", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def export_sales_csv(
    status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    dt_from: Optional[str] = Query(None),
    dt_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    request: Request = None,
):
    from datetime import datetime as _dt
    stmt = select(Sale).order_by(Sale.id.desc())
    if status:
        stmt = stmt.where(Sale.status == status)
    if customer_id:
        stmt = stmt.where(Sale.customer_id == int(customer_id))
    if dt_from:
        try:
            d = _dt.fromisoformat(dt_from.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date >= d)
        except Exception:
            pass
    if dt_to:
        try:
            d = _dt.fromisoformat(dt_to.replace("Z", "+00:00"))
            stmt = stmt.where(Sale.sale_date <= d)
        except Exception:
            pass
    rows = (await db.execute(stmt)).scalars().all()
    _audit(db, "sale_export_csv", "sales", None, {
        "filters": {"status": status, "customer_id": customer_id, "dt_from": dt_from, "dt_to": dt_to},
        "rows": len(rows)
    }, sess, request)
    await db.commit()
    filename = "sales_export.csv"
    return StreamingResponse(_iter_sales_csv(rows), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })


# --- Autocomplete productos (catálogo) ---
@router.get("/catalog/search", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def catalog_search(q: str = Query(..., min_length=1), limit: int = Query(15, ge=1, le=100), db: AsyncSession = Depends(get_session)):
    term = q.strip()
    like = f"%{term}%"
    # Estrategia: priorizar productos con stock > 0 y término en título o canonical_sku (fallback a sku_root).
    # Buscar primero por canonical_sku, luego por sku_root como fallback temporal
    stmt = select(Product).where(
        or_(
            Product.title.ilike(like),
            Product.canonical_sku.ilike(like),
            Product.sku_root.ilike(like)
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    scored = []
    for p in rows:
        score = 0
        t_low = p.title.lower() if p.title else ""
        if term.lower() in t_low:
            score += 50
        if t_low.startswith(term.lower()):
            score += 30
        if p.stock and p.stock > 0:
            score += 40
        else:
            score -= 10
        scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    items = []
    for s, p in scored[:limit]:
        price = None
        if p.variants:
            v = p.variants[0]
            price = float(v.promo_price or v.price or 0)
        items.append({
            "product_id": p.id,
            "canonical": True,  # Placeholder (futuro: distinguir canónico)
            "title": p.title,
            "sku": p.canonical_sku or p.sku_root,  # Priorizar canonical_sku
            "price": price,
            "stock": p.stock,
            "score": s,
        })
    return {"query": term, "items": items, "count": len(items)}


@router.get("/reports/margin", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_margin_report(
    dt_from: datetime | None = None,
    dt_to: datetime | None = None,
    channel_id: int | None = None,
    db: AsyncSession = Depends(get_session),
):
    stmt = (
        select(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(Sale.status.in_(["CONFIRMADA", "ENTREGADA"]))
    )
    if dt_from:
        stmt = stmt.where(Sale.sale_date >= dt_from)
    if dt_to:
        stmt = stmt.where(Sale.sale_date <= dt_to)
    if channel_id:
        stmt = stmt.where(Sale.channel_id == channel_id)
    lines = (await db.execute(stmt)).scalars().all()
    revenue = Decimal("0")
    cost = Decimal("0")
    covered_revenue = Decimal("0")
    for line in lines:
        line_revenue = Decimal(str(line.total or 0)) - Decimal(str(line.global_discount_allocated or 0))
        revenue += line_revenue
        if line.unit_cost_snapshot is not None:
            cost += Decimal(str(line.unit_cost_snapshot)) * Decimal(str(line.qty))
            covered_revenue += line_revenue
    margin = revenue - cost
    return {
        "revenue": float(money(revenue)),
        "cost": float(money(cost)),
        "margin": float(money(margin)),
        "margin_percent": float(money((margin / revenue * 100) if revenue else 0)),
        "cost_coverage_percent": float(money((covered_revenue / revenue * 100) if revenue else 0)),
        "lines": len(lines),
    }


@router.get("/reports/channels", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def sales_channels_report(db: AsyncSession = Depends(get_session)):
    rows = (
        await db.execute(
            select(
                Sale.channel_id,
                SalesChannel.name,
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0),
            )
            .outerjoin(SalesChannel, SalesChannel.id == Sale.channel_id)
            .where(Sale.status.in_(["CONFIRMADA", "ENTREGADA"]))
            .group_by(Sale.channel_id, SalesChannel.name)
            .order_by(func.sum(Sale.total_amount).desc())
        )
    ).all()
    return {
        "items": [
            {"channel_id": channel_id, "channel_name": name or "Sin canal", "sales_count": count, "total": float(total)}
            for channel_id, name, count, total in rows
        ]
    }


def _normalize_router_routes() -> None:
    """Retira registros duplicados legacy y prioriza rutas estáticas sobre parámetros."""
    seen: set[tuple[str, tuple[str, ...]]] = set()
    unique = []
    for route in router.routes:
        methods = tuple(sorted(getattr(route, "methods", set())))
        key = (getattr(route, "path", ""), methods)
        if key in seen:
            continue
        seen.add(key)
        unique.append(route)
    unique.sort(key=lambda route: ("{" in getattr(route, "path", ""), getattr(route, "path", "")))
    router.routes[:] = unique


_normalize_router_routes()
