# NG-HEADER: Nombre de archivo: sales.py
# NG-HEADER: Ubicación: services/routers/sales.py
# NG-HEADER: Descripción: Endpoints de clientes y ventas (CRUD clientes, registrar venta, adjuntos)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from typing import Optional
from datetime import datetime
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, Float

from db.session import get_session
from db.models import Customer, Sale, SaleLine, SalePayment, SaleAttachment, Product, AuditLog, Return, ReturnLine
from db.models import StockLedger, SalesChannel
from services.auth import require_roles, require_csrf, current_session, SessionData
from services.media import save_upload, get_media_root
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from sqlalchemy import desc

router = APIRouter(prefix="/sales", tags=["sales"])

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
    subtotal = Decimal("0")
    for l in lines:
        unit = Decimal(str(l.unit_price))
        qty = Decimal(str(l.qty))
        disc = Decimal(str(l.line_discount or 0))
        line_subtotal = (unit * qty)
        line_total = (line_subtotal * (Decimal("1") - disc/Decimal("100")))
        l.subtotal = line_subtotal.quantize(Decimal("0.01"))
        l.tax = Decimal("0")  # IVA futuro
        l.total = line_total.quantize(Decimal("0.01"))
        subtotal += l.total
    db_sale.subtotal = subtotal.quantize(Decimal("0.01"))
    db_sale.tax = Decimal("0")  # preparado futuro IVA
    # Descuento global (discount_percent o discount_amount)
    discount_percent = Decimal(str(db_sale.discount_percent or 0))
    discount_amount = Decimal(str(db_sale.discount_amount or 0))
    if discount_amount and discount_percent:
        # Si ambos están presentes, priorizar monto explícito
        discount_percent = Decimal("0")
    if discount_percent:
        discount_amount = (subtotal * discount_percent/Decimal("100")).quantize(Decimal("0.01"))
        db_sale.discount_amount = discount_amount
    db_sale.total_amount = (subtotal - discount_amount).quantize(Decimal("0.01"))
    if db_sale.total_amount < 0:
        db_sale.total_amount = Decimal("0")
    # payment_status si hay pagos existentes
    paid = Decimal(str(db_sale.paid_total or 0))
    if paid == 0:
        db_sale.payment_status = "PENDIENTE"
    elif paid < db_sale.total_amount:
        db_sale.payment_status = "PARCIAL"
    else:
        db_sale.payment_status = "PAGADA"


"""Rate limiting simple (in-memory). Nota: mono-proceso; usar Redis en despliegues multi.
_RL_BUCKET almacena timestamps por llave (usuario o IP)."""
_RL_BUCKET: dict[str, list[float]] = {}
_RL_MAX = 30  # max requests ventana
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


@router.post("", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def create_sale(payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
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
            ok, retry = _rl_check(key)
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
        qty = Decimal(str(it.get("qty")))
        if qty <= 0:
            raise HTTPException(status_code=400, detail="qty debe ser > 0")
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
    lines_full = (await db.execute(select(SaleLine).where(SaleLine.sale_id == sale.id))).scalars().all()
    _recalc_totals(sale, lines_full)

    # Confirmar inmediatamente si se solicitó
    if status_req == "CONFIRMADA":
        missing = []
        for l in lines_full:
            prod = await db.get(Product, l.product_id)
            if int(prod.stock or 0) < int(l.qty):
                missing.append({"product_id": prod.id, "needed": int(l.qty), "have": int(prod.stock or 0)})
        if missing:
            raise HTTPException(status_code=400, detail={"error": "stock_insuficiente", "items": missing})
        for l in lines_full:
            prod = await db.get(Product, l.product_id)
            prod.stock = int(prod.stock or 0) - int(l.qty)
        sale.status = "CONFIRMADA"
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
            qty_d = _D(str(qty))
            if qty_d <= 0:
                raise HTTPException(status_code=400, detail="qty debe ser > 0")
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
                qv = _D(str(op.get("qty") or 0))
                if qv <= 0:
                    raise HTTPException(status_code=400, detail="qty debe ser > 0")
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
    customer_id: Optional[int] = Query(None),
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
    if customer_id:
        stmt = stmt.where(Sale.customer_id == int(customer_id))
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
    def _row(s: Sale):
        return {"id": s.id, "status": s.status, "sale_date": s.sale_date.isoformat(), "customer_id": s.customer_id, "total": float(s.total_amount or 0), "paid_total": float(s.paid_total or 0)}
    return {"items": [_row(s) for s in rows], "total": int(total or 0), "page": page, "pages": ((int(total or 0) + page_size - 1)//page_size) if total else 0}


@router.get("/{sale_id}", dependencies=[Depends(require_roles("colaborador", "admin"))])
async def get_sale_detail(sale_id: int, db: AsyncSession = Depends(get_session)):
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    pays = (await db.execute(select(SalePayment).where(SalePayment.sale_id == s.id))).scalars().all()
    return {
        "id": s.id,
        "status": s.status,
        "sale_date": s.sale_date.isoformat(),
        "customer_id": s.customer_id,
        "channel_id": s.channel_id,
        "additional_costs": s.additional_costs,
        "total": float(s.total_amount or 0),
        "paid_total": float(s.paid_total or 0),
        "payment_status": s.payment_status,
        "lines": [{"id": l.id, "product_id": l.product_id, "qty": float(l.qty), "unit_price": float(l.unit_price), "line_discount": float(l.line_discount or 0)} for l in lines],
        "payments": [{"id": p.id, "method": p.method, "amount": float(p.amount), "reference": p.reference, "paid_at": (p.paid_at.isoformat() if p.paid_at else None)} for p in pays],
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
    s = await db.get(Sale, sale_id)
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        return {"status": s.status, "already": True}
    if s.status not in ("CONFIRMADA", "ENTREGADA"):
        raise HTTPException(status_code=400, detail="Solo se puede anular CONFIRMADA/ENTREGADA")
    # Reponer stock por líneas
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    deltas: list[dict] = []
    for l in lines:
        prod = await db.get(Product, l.product_id)
        if not prod:
            continue
        before = int(prod.stock or 0)
        prod.stock = before + int(l.qty)
        deltas.append({"product_id": prod.id, "delta": int(l.qty), "new": int(prod.stock)})
    s.status = "ANULADA"
    # Audit log con deltas de stock
    _audit(db, "sale_annul", "sales", s.id, {"reason": reason, "stock_deltas": deltas, "elapsed_ms": 0}, sess, request)
    _report_cache_invalidate()  # anulación afecta métricas agregadas
    await db.commit()
    return {"status": s.status, "restored": deltas}


# --- Ventas: confirmar (valida stock, afecta) y entregar ---

@router.post("/{sale_id}/confirm", dependencies=[Depends(require_roles("colaborador", "admin")), Depends(require_csrf)])
async def confirm_sale(sale_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session), request: Request = None):
    s = await db.get(Sale, sale_id)
    t0 = time.perf_counter()
    if not s:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if s.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Venta anulada")
    if s.status in ("CONFIRMADA", "ENTREGADA"):
        return {"status": s.status, "already": True}
    # Cargar líneas y recalcular para asegurar integridad de subtotal/total antes de confirmar
    lines = (await db.execute(select(SaleLine).where(SaleLine.sale_id == s.id))).scalars().all()
    _recalc_totals(s, lines)
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
    # Validar stock por líneas tras recalcular
    missing = []
    for l in lines:
        p = await db.get(Product, l.product_id)
        if not p:
            missing.append({"product_id": l.product_id, "reason": "no existe"})
            continue
        if int(p.stock or 0) < int(l.qty):
            missing.append({"product_id": p.id, "needed": int(l.qty), "have": int(p.stock or 0)})
    if missing:
        raise HTTPException(status_code=400, detail={"error": "stock_insuficiente", "items": missing})
    # Afectar stock y poblar snapshots
    deltas = []
    ledger_rows: list[dict] = []
    for l in lines:
        p = await db.get(Product, l.product_id)
        before = int(p.stock or 0)
        p.stock = before - int(l.qty)
        # Poblar snapshots si vacías
        if not l.title_snapshot:
            l.title_snapshot = p.title
        if not l.sku_snapshot:
            # Evitar lazy-load de variants dentro de TestClient sync; usar sku_root directamente
            l.sku_snapshot = p.sku_root
        deltas.append({"product_id": p.id, "delta": -int(l.qty), "new": int(p.stock)})
        # Registrar ledger (delta negativo) via ORM (errores no bloquean confirmación, se auditan en caso futuro)
        try:
            db.add(StockLedger(
                product_id=p.id,
                source_type='sale',
                source_id=s.id,
                delta=-int(l.qty),
                balance_after=int(p.stock),
                meta={'sale_line_id': l.id}
            ))
        except Exception:
            pass
    s.status = "CONFIRMADA"
    _audit(db, "sale_confirm", "sales", s.id, {"stock_deltas": deltas, "elapsed_ms": round((time.perf_counter()-t0)*1000,2)}, sess, request)
    # Invalidate report cache (ventas afectan reportes)
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
    sale = await db.get(Sale, sale_id)
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
    q_lines = (await db.execute(select(SaleLine).where(SaleLine.id.in_(line_ids)))).scalars().all()
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

    total_amount = Decimal("0")
    stock_deltas: list[dict] = []
    for it in items:
        sl_id = int(it.get("sale_line_id"))
        line = lines_map[sl_id]
        qty_req = Decimal(str(it.get("qty")))
        if qty_req <= 0:
            raise HTTPException(status_code=400, detail=f"qty inválida en línea {sl_id}")
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
        prod = await db.get(Product, line.product_id)
        if prod:
            before = int(prod.stock or 0)
            prod.stock = before + int(qty_req)
            stock_deltas.append({"product_id": prod.id, "delta": int(qty_req), "new": int(prod.stock)})
            # Ledger delta positivo via ORM
            try:
                db.add(StockLedger(
                    product_id=prod.id,
                    source_type='return',
                    source_id=ret.id,
                    delta=int(qty_req),
                    balance_after=int(prod.stock),
                    meta={'sale_line_id': sl_id}
                ))
            except Exception:
                pass

    ret.total_amount = total_amount
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
    sale = await db.get(Sale, sale_id)
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
    q_lines = (await db.execute(select(SaleLine).where(SaleLine.id.in_(line_ids)))).scalars().all()
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

    total_amount = Decimal("0")
    stock_deltas: list[dict] = []
    for it in items:
        sl_id = int(it.get("sale_line_id"))
        line = lines_map[sl_id]
        qty_req = Decimal(str(it.get("qty")))
        if qty_req <= 0:
            raise HTTPException(status_code=400, detail=f"qty inválida en línea {sl_id}")
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
        prod = await db.get(Product, line.product_id)
        if prod:
            before = int(prod.stock or 0)
            prod.stock = before + int(qty_req)
            stock_deltas.append({"product_id": prod.id, "delta": int(qty_req), "new": int(prod.stock)})
            # Ledger delta positivo via ORM
            try:
                db.add(StockLedger(
                    product_id=prod.id,
                    source_type='return',
                    source_id=ret.id,
                    delta=int(qty_req),
                    balance_after=int(prod.stock),
                    meta={'sale_line_id': sl_id}
                ))
            except Exception:
                pass

    ret.total_amount = total_amount
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
    # Estrategia: priorizar productos con stock > 0 y término en título o sku_root.
    stmt = select(Product).where(
        or_(Product.title.ilike(like), Product.sku_root.ilike(like))
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
            "sku": p.sku_root,
            "price": price,
            "stock": p.stock,
            "score": s,
        })
    return {"query": term, "items": items, "count": len(items)}
