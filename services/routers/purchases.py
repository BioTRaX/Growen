# NG-HEADER: Nombre de archivo: purchases.py
# NG-HEADER: Ubicación: services/routers/purchases.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Compras (purchases) API endpoints.

Estados de compra: BORRADOR -> VALIDADA -> CONFIRMADA -> ANULADA.
Incluye: crear/editar, validación, confirmación (impacta stock y buy_price),
anulación, listado con filtros, importación Santa Planta (PDF) y export de
líneas SIN_VINCULAR.
"""
from __future__ import annotations

from datetime import date, datetime
import re
import os
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from db.session import get_session
from db.models import (
    Purchase,
    PurchaseLine,
    Supplier,
    SupplierProduct,
    PriceHistory,
    AuditLog,
    Product,
    PurchaseAttachment,
    ImportLog,
)
from services.auth import require_roles, require_csrf, SessionData, current_session
from services.suppliers.santaplanta_pdf import parse_santaplanta_pdf
from services.importers.santaplanta_pipeline import parse_remito
import httpx
import hashlib
import uuid

router = APIRouter(prefix="/purchases", tags=["purchases"]) 


@router.post("", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def create_purchase(payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    supplier_id = payload.get("supplier_id")
    remito_number = payload.get("remito_number")
    remito_date = payload.get("remito_date")
    if not supplier_id or not remito_number or not remito_date:
        raise HTTPException(status_code=400, detail="supplier_id, remito_number y remito_date son obligatorios")
    # Unicidad por (supplier_id, remito_number)
    exists = await db.scalar(select(Purchase).where(Purchase.supplier_id==supplier_id, Purchase.remito_number==remito_number))
    if exists:
        raise HTTPException(status_code=409, detail="Compra ya existe para ese proveedor y remito")
    p = Purchase(
        supplier_id=supplier_id,
        remito_number=remito_number,
        remito_date=date.fromisoformat(remito_date),
        global_discount=payload.get("global_discount") or 0,
        vat_rate=payload.get("vat_rate") or 0,
        note=payload.get("note"),
        created_by=sess.user.id if sess.user else None,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "status": p.status}


@router.put("/{purchase_id}", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def update_purchase(purchase_id: int, payload: dict, db: AsyncSession = Depends(get_session)):
    p = await db.get(Purchase, purchase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    # Encabezado
    for k in ("global_discount", "vat_rate", "note", "remito_date", "depot_id", "remito_number"):
        if k in payload and payload[k] is not None:
            if k == "remito_date" and isinstance(payload[k], str):
                try:
                    p.remito_date = date.fromisoformat(payload[k])
                except ValueError:
                    raise HTTPException(status_code=400, detail="remito_date inválida")
            else:
                setattr(p, k, payload[k])

    # Líneas: upsert/delete
    lines: list[dict[str, Any]] = payload.get("lines") or []
    for ln in lines:
        op = (ln.get("op") or "upsert").lower()
        lid = ln.get("id")
        if op == "delete" and lid:
            obj = await db.get(PurchaseLine, int(lid))
            if obj and obj.purchase_id == p.id:
                await db.delete(obj)
            continue
        # upsert
        if lid:
            obj = await db.get(PurchaseLine, int(lid))
            if not obj or obj.purchase_id != p.id:
                raise HTTPException(status_code=404, detail="Línea no encontrada")
        else:
            obj = PurchaseLine(purchase_id=p.id)
            db.add(obj)
        for k in ("supplier_item_id", "product_id", "supplier_sku", "title", "qty", "unit_cost", "line_discount", "state", "note"):
            if k in ln:
                setattr(obj, k, ln[k])

    await db.commit()
    return {"status": "ok"}


@router.get("")
async def list_purchases(
    db: AsyncSession = Depends(get_session),
    supplier_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    depot_id: Optional[int] = Query(None),
    remito_number: Optional[str] = Query(None),
    product_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    stmt = select(Purchase)
    if supplier_id:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
    if status:
        stmt = stmt.where(Purchase.status == status)
    if depot_id is not None:
        stmt = stmt.where(Purchase.depot_id == depot_id)
    if remito_number:
        stmt = stmt.where(Purchase.remito_number.ilike(f"%{remito_number}%"))
    if date_from:
        try:
            df = date.fromisoformat(date_from)
            stmt = stmt.where(Purchase.remito_date >= df)
        except Exception:
            raise HTTPException(status_code=400, detail="date_from inválida")
    if date_to:
        try:
            dt = date.fromisoformat(date_to)
            stmt = stmt.where(Purchase.remito_date <= dt)
        except Exception:
            raise HTTPException(status_code=400, detail="date_to inválida")
    if product_name:
        # Join con líneas para buscar por título
        sub = select(PurchaseLine.purchase_id).where(PurchaseLine.title.ilike(f"%{product_name}%")).subquery()
        stmt = stmt.where(Purchase.id.in_(select(sub.c.purchase_id)))

    count = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Purchase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": r.id,
            "supplier_id": r.supplier_id,
            "remito_number": r.remito_number,
            "status": r.status,
            "remito_date": r.remito_date.isoformat(),
        }
        for r in rows
    ]
    return {"items": items, "total": count or 0, "page": page, "pages": (int(((count or 0) + page_size - 1) / page_size) if page_size else 1)}


@router.get("/{purchase_id}")
async def get_purchase(purchase_id: int, db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines), selectinload(Purchase.attachments))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    from decimal import Decimal
    vat_rate = Decimal(str(p.vat_rate or 0)) / Decimal("100")
    subtotal = Decimal("0")
    for l in p.lines:
        qty = Decimal(str(l.qty or 0))
        unit = Decimal(str(l.unit_cost or 0))
        disc = Decimal(str(l.line_discount or 0)) / Decimal("100")
        eff = unit * (Decimal("1") - disc)
        subtotal += qty * eff
    iva = (subtotal * vat_rate).quantize(Decimal("0.01"))
    total = (subtotal + iva).quantize(Decimal("0.01"))
    return {
        "id": p.id,
        "supplier_id": p.supplier_id,
        "remito_number": p.remito_number,
        "remito_date": p.remito_date.isoformat(),
        "status": p.status,
    "meta": getattr(p, "meta", {}) or {},
        "global_discount": float(p.global_discount or 0),
        "vat_rate": float(p.vat_rate or 0),
        "note": p.note,
        "depot_id": p.depot_id,
        "totals": {"subtotal": float(subtotal), "iva": float(iva), "total": float(total)},
        "lines": [
            {
                "id": l.id,
                "supplier_item_id": l.supplier_item_id,
                "product_id": l.product_id,
                "supplier_sku": l.supplier_sku,
                "title": l.title,
                "qty": float(l.qty or 0),
                "unit_cost": float(l.unit_cost or 0),
                "line_discount": float(l.line_discount or 0),
                "state": l.state,
                "note": l.note,
                "computed": {
                    "subtotal": float(Decimal(str(l.qty or 0)) * Decimal(str(l.unit_cost or 0)) * (Decimal("1") - Decimal(str(l.line_discount or 0))/Decimal("100")))
                }
            }
            for l in p.lines
        ],
        "attachments": [
            {
                "id": a.id,
                "filename": a.filename,
                "mime": a.mime,
                "size": a.size,
                "path": a.path,
                "url": f"/purchases/{p.id}/attachments/{a.id}/file",
            }
            for a in p.attachments
        ],
    }


@router.post("/{purchase_id}/validate", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def validate_purchase(purchase_id: int, db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    # Chequear unicidad supplier+remito (excluyendo esta compra)
    dup = await db.scalar(select(Purchase).where(Purchase.id != p.id, Purchase.supplier_id == p.supplier_id, Purchase.remito_number == p.remito_number))
    if dup:
        raise HTTPException(status_code=409, detail="Compra ya existe para ese proveedor y remito")

    total_lines = len(p.lines)
    unmatched = 0
    for l in p.lines:
        linked = bool(l.product_id or l.supplier_item_id)
        l.state = "OK" if linked else "SIN_VINCULAR"
        if not linked:
            unmatched += 1
    # Requiere al menos 1 línea para quedar VALIDADA
    p.status = "VALIDADA" if (unmatched == 0 and total_lines > 0) else "BORRADOR"
    await db.commit()
    return {"status": "ok", "unmatched": unmatched, "lines": total_lines}


@router.post("/{purchase_id}/confirm", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def confirm_purchase(purchase_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if not p.lines:
        raise HTTPException(status_code=422, detail="No hay lineas para confirmar")
    if p.status == "CONFIRMADA":
        return {"status": "ok"}

    now = datetime.utcnow()
    # Impactar stock y buy_price + price_history
    for l in p.lines:
        # Ajuste de costo por descuentos
        ln_disc = Decimal(str(l.line_discount or 0)) / Decimal("100")
        unit_cost = Decimal(str(l.unit_cost or 0))
        eff = unit_cost * (Decimal("1") - ln_disc)

        # Actualizar precio de compra del supplier_item
        if l.supplier_item_id:
            sp = await db.get(SupplierProduct, l.supplier_item_id)
            if sp:
                old = Decimal(str(sp.current_purchase_price or 0))
                sp.current_purchase_price = eff
                ph = PriceHistory(
                    entity_type="supplier",
                    entity_id=sp.id,
                    price_old=old,
                    price_new=eff,
                    note=f"Compra #{p.id} remito {p.remito_number}",
                    user_id=sess.user.id if sess.user else None,
                    ip=None,
                )
                db.add(ph)

        # Impacto en stock a nivel producto
        prod_id: Optional[int] = l.product_id
        if not prod_id and l.supplier_item_id:
            sp = sp if 'sp' in locals() and sp and sp.id == l.supplier_item_id else await db.get(SupplierProduct, l.supplier_item_id)
            if sp and sp.internal_product_id:
                prod_id = sp.internal_product_id
        if prod_id:
            prod = await db.get(Product, prod_id)
            if prod:
                # suma de stock
                try:
                    qty = int(Decimal(str(l.qty or 0)))
                except Exception:
                    qty = int(l.qty or 0)
                prod.stock = int(prod.stock or 0) + max(0, qty)

    p.status = "CONFIRMADA"
    # Log resumen + deltas de stock
    stock_deltas = []
    for l in p.lines:
        try:
            q = int(Decimal(str(l.qty or 0)))
        except Exception:
            q = int(l.qty or 0)
        target = l.product_id
        if not target and l.supplier_item_id:
            sp = await db.get(SupplierProduct, l.supplier_item_id)
            if sp and sp.internal_product_id:
                target = sp.internal_product_id
        if target:
            stock_deltas.append({"product_id": target, "delta": int(max(0, q))})
    db.add(
        AuditLog(
            action="purchase_confirm",
            table="purchases",
            entity_id=p.id,
            meta={"lines": len(p.lines), "stock_deltas": stock_deltas},
            user_id=sess.user.id if sess.user else None,
            ip=None,
        )
    )
    await db.commit()

    # Notificación Telegram opcional
    token = os.getenv("PURCHASE_TELEGRAM_TOKEN")
    chat_id = os.getenv("PURCHASE_TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            text = f"Compra confirmada: proveedor {p.supplier_id}, remito {p.remito_number}, líneas {len(p.lines)}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text})
        except Exception:
            pass
    return {"status": "ok"}


@router.post("/{purchase_id}/cancel", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def cancel_purchase(purchase_id: int, payload: dict, db: AsyncSession = Depends(get_session)):
    note = payload.get("note")
    if not note:
        raise HTTPException(status_code=400, detail="note es obligatoria para anular")
    res = await db.execute(
        select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    # Revertir stock si estaba confirmada
    reverted = []
    if p.status == "CONFIRMADA":
        for l in p.lines:
            target = l.product_id
            if not target and l.supplier_item_id:
                sp = await db.get(SupplierProduct, l.supplier_item_id)
                if sp and sp.internal_product_id:
                    target = sp.internal_product_id
            if not target:
                continue
            prod = await db.get(Product, target)
            if not prod:
                continue
            try:
                qty = int(Decimal(str(l.qty or 0)))
            except Exception:
                qty = int(l.qty or 0)
            prod.stock = int(prod.stock or 0) - max(0, qty)
            reverted.append({"product_id": target, "delta": -int(max(0, qty))})
    p.status = "ANULADA"
    p.note = (p.note or "") + f"\nANULADA: {note}"
    db.add(
        AuditLog(
            action="purchase_annul",
            table="purchases",
            entity_id=p.id,
            meta={"note": note, "reverted": reverted},
            user_id=None,
            ip=None,
        )
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/import/santaplanta", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def import_santaplanta_pdf(
    supplier_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    debug: int = Query(0),
    force_ocr: int = Query(0),
):
    import logging
    log = logging.getLogger("growen")
    try:
        content = await file.read()
        # Validar tipo PDF por content-type o magic header
        ct = (file.content_type or "").lower() if hasattr(file, "content_type") else ""
        if not ("pdf" in ct or (len(content) >= 4 and content[:4] == b"%PDF")):
            raise HTTPException(status_code=400, detail="Se espera un PDF")
        sha256 = hashlib.sha256(content).hexdigest()
        correlation_id = uuid.uuid4().hex
        debug_flag = bool(debug) or (os.getenv("IMPORT_RETURN_DEBUG", "0") in ("1", "true", "True"))
        # Guardar a disco primero y usar el pipeline robusto
        tmp_root = Path("data") / "purchases" / "_tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_pdf = tmp_root / (uuid.uuid4().hex + ".pdf")
        with open(tmp_pdf, "wb") as fh:
            fh.write(content)

        # Log start (sin purchase_id aún)
        try:
            db.add(
                AuditLog(
                    action="purchase_import_start",
                    table="purchases",
                    entity_id=None,
                    meta={
                        "correlation_id": correlation_id,
                        "supplier_id": supplier_id,
                        "filename": file.filename,
                        "size": len(content),
                        "sha256": sha256,
                    },
                    user_id=None,
                    ip=None,
                )
            )
            await db.flush()
        except Exception:
            pass

        log.info(f"Import[{correlation_id}]: Iniciando pipeline para {tmp_pdf} (size={len(content)}, sha256={sha256}, force_ocr={force_ocr})")

        # Ejecutar pipeline (pdfplumber -> camelot -> OCR -> reintentos)
        res = parse_remito(
            tmp_pdf,
            correlation_id=correlation_id,
            use_ocr_auto=True,
            force_ocr=bool(force_ocr),
            debug=debug_flag,
        )
        log.info(f"Import[{correlation_id}]: Pipeline finalizado. Remito={res.remito_number}, Fecha={res.remito_date}, Líneas detectadas={len(res.lines) if res.lines else 0}")

        remito_number = res.remito_number or file.filename
        remito_date_str = res.remito_date
        try:
            remito_dt = date.fromisoformat(remito_date_str) if remito_date_str else date.today()
        except Exception:
            remito_dt = date.today()

        if not res.lines:
            try:
                db.add(
                    AuditLog(
                        action="purchase_import_no_lines",
                        table="purchases",
                        entity_id=None,
                        meta={
                            "correlation_id": correlation_id,
                            "supplier_id": supplier_id,
                            "filename": file.filename,
                            "sha256": sha256,
                            "remito": res.remito_number,
                            "fecha": res.remito_date,
                            "events": (res.events[:20] if res.events else []),
                        },
                        user_id=None,
                        ip=None,
                    )
                )
                await db.commit()
            except Exception:
                pass
            detail = {
                "detail": "No se detectaron líneas. Revisá el PDF del proveedor.",
                "correlation_id": correlation_id,
                "remito": res.remito_number,
                "fecha": res.remito_date,
            }
            if debug:
                detail["events"] = res.events[:20] if res.events else []
                if res.debug:
                    detail["debug"] = {"samples": res.debug.get("samples")}
            raise HTTPException(status_code=422, detail=detail)

        # Idempotencia: UNIQUE (supplier_id, remito_number)
        exists = await db.scalar(select(Purchase).where(Purchase.supplier_id==supplier_id, Purchase.remito_number==remito_number))
        if exists:
            raise HTTPException(status_code=409, detail="Compra ya existe para ese proveedor y remito")
        # Idempotencia adicional: mismo PDF (hash) para el mismo proveedor
        dup_q = (
            select(PurchaseAttachment)
            .join(Purchase, PurchaseAttachment.purchase_id == Purchase.id)
            .where(Purchase.supplier_id == supplier_id)
        )
        dup_atts = (await db.execute(dup_q)).scalars().all()
        for att in dup_atts:
            try:
                with open(att.path, "rb") as fh:
                    other = hashlib.sha256(fh.read()).hexdigest()
                if other == sha256:
                    db.add(
                        AuditLog(
                            action="purchase_import_duplicate",
                            table="purchases",
                            entity_id=att.purchase_id,
                            meta={"correlation_id": correlation_id, "sha256": sha256, "filename": file.filename},
                            user_id=None,
                            ip=None,
                        )
                    )
                    await db.commit()
                    raise HTTPException(status_code=409, detail="PDF ya importado para este proveedor")
            except FileNotFoundError:
                continue

        p = Purchase(supplier_id=supplier_id, remito_number=remito_number, remito_date=remito_dt)
        db.add(p)
        await db.flush()

        # Guardar el adjunto
        root = Path("data") / "purchases" / str(p.id)
        root.mkdir(parents=True, exist_ok=True)
        pdf_path = root / file.filename
        with open(pdf_path, "wb") as fh:
            fh.write(content)

        db.add(PurchaseAttachment(purchase_id=p.id, filename=file.filename, mime=file.content_type, size=len(content), path=str(pdf_path)))

        # Crear líneas con matching por supplier_sku -> supplier_products.supplier_product_id
        # Convertir líneas normalizadas del parser
        lines = [
            {
                "supplier_sku": ln.supplier_sku,
                "title": ln.title,
                "qty": float(ln.qty),
                "unit_cost": float(ln.unit_cost_bonif),
                "line_discount": float(ln.pct_bonif),
                "subtotal": float(ln.subtotal or (ln.qty * ln.unit_cost_bonif)),
                "iva": float(ln.iva or 0),
                "total": float(ln.total or (ln.subtotal or (ln.qty * ln.unit_cost_bonif))),
            }
            for ln in res.lines
        ]
        for ln in lines:
            sku = (ln.get("supplier_sku") or "").strip()
            title = (ln.get("title") or "").strip() or sku or "(sin título)"
            qty = Decimal(str(ln.get("qty") or 0))
            unit_cost = Decimal(str(ln.get("unit_cost") or 0))
            line_discount = Decimal(str(ln.get("line_discount") or 0))
            supplier_item_id = None
            product_id = None
            if sku:
                sp = await db.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id==supplier_id, SupplierProduct.supplier_product_id==sku))
                if sp:
                    supplier_item_id = sp.id
                    product_id = sp.internal_product_id
            # Tolerante: si no hay SKU o no matchea, intentar por título (búsqueda simple)
            if not supplier_item_id and title and len(title) >= 6:
                # Buscar candidatos por palabra clave larga para limitar universo
                try:
                    key = max((w for w in re.split(r"\W+", title) if len(w) >= 5), key=len)
                except ValueError:
                    key = title.split(" ")[0]
                cand_q = select(SupplierProduct).where(
                    SupplierProduct.supplier_id==supplier_id,
                    SupplierProduct.title.ilike(f"%{key}%")
                ).limit(15)
                cands = (await db.execute(cand_q)).scalars().all()
                if cands:
                    # Elegir el más parecido con difflib, con umbral 0.85 y ambigüedad controlada
                    try:
                        import difflib
                        scored = []
                        for c in cands:
                            r = difflib.SequenceMatcher(None, (c.title or "").lower(), title.lower()).ratio()
                            scored.append((r, c))
                        scored.sort(reverse=True, key=lambda x: x[0])
                        if scored and scored[0][0] >= 0.85:
                            if len(scored) == 1 or (scored[0][0] - scored[1][0]) >= 0.05:
                                supplier_item_id = scored[0][1].id
                                product_id = scored[0][1].internal_product_id
                    except Exception:
                        pass
            state = "OK" if (supplier_item_id or product_id) else "SIN_VINCULAR"
            db.add(PurchaseLine(
                purchase_id=p.id,
                supplier_item_id=supplier_item_id,
                product_id=product_id,
                supplier_sku=sku or None,
                title=title,
                qty=qty,
                unit_cost=unit_cost,
                line_discount=line_discount,
                state=state,
            ))

        # Persistir meta resumen y log con correlation_id
        try:
            setattr(p, "meta", {
                "correlation_id": correlation_id,
                "filename": file.filename,
                "sha256": sha256,
                "remito_number": remito_number,
                "remito_date": remito_dt.isoformat(),
                "lines_detected": len(lines),
            })
        except Exception:
            pass
        # Log de import con resumen, correlation_id y muestras
        db.add(
            AuditLog(
                action="purchase_import",
                table="purchases",
                entity_id=p.id,
                meta={
                    "correlation_id": correlation_id,
                    "filename": file.filename,
                    "sha256": sha256,
                    "remito_number": remito_number,
                    "remito_date": remito_dt.isoformat(),
                    "lines_detected": len(lines),
                    "samples": (res.debug.get("samples") if debug_flag else None),
                },
                user_id=None,
                ip=None,
            )
        )
        # Persistir eventos detallados si el modelo está disponible
        try:
            for ev in res.events:
                db.add(
                    ImportLog(
                        purchase_id=p.id,
                        correlation_id=correlation_id,
                        level=str(ev.get("level") or "INFO"),
                        stage=str(ev.get("stage") or ""),
                        event=str(ev.get("event") or ""),
                        details=ev.get("details") or {},
                    )
                )
        except Exception:
            pass
        await db.commit()
        await db.refresh(p)
        # Calcular totales simples desde líneas
        try:
            sub = float(res.totals.get("subtotal") or 0)
        except Exception:
            sub = sum(float(l.get("subtotal") or 0) for l in lines) or sum(
                float(l.get("qty") or 0) * float(l.get("unit_cost") or 0) for l in lines
            )
        vat = float(p.vat_rate or 0)
        iva = sub * (vat / 100.0)
        total = sub + iva
        return {
            "purchase_id": p.id,
            "status": p.status,
            "filename": file.filename,
            "correlation_id": correlation_id,
            "parsed": {
                "remito": remito_number,
                "fecha": remito_dt.isoformat(),
                "lines": len(lines),
                "totals": {"subtotal": round(sub, 2), "iva": round(iva, 2), "total": round(total, 2)},
                "hash": f"sha256:{sha256}",
            },
            "unmatched_count": 0,
            "debug": (res.debug if debug_flag else None),
        }
    except HTTPException:
        # Re-raise known API errors without logging stack
        raise
    except Exception as e:
        # Log full context to backend.log to help diagnose
        try:
            log.exception("Error importando Santaplanta PDF: supplier_id=%s, filename=%s", supplier_id, getattr(file, "filename", "?"))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="No se pudo importar el remito; revisá backend.log para más detalles")


@router.get("/{purchase_id}/unmatched/export")
async def export_unmatched(purchase_id: int, fmt: str = Query("csv"), db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    rows = [
        [l.supplier_sku or "", l.title or "", float(l.qty or 0), float(l.unit_cost or 0), float(l.line_discount or 0), l.note or ""]
        for l in p.lines
        if not (l.product_id or l.supplier_item_id)
    ]
    header = ["supplier_sku", "title", "qty", "unit_cost", "line_discount", "note"]
    if fmt == "xlsx":
        try:
            import io
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.append(header)
            for r in rows:
                ws.append(r)
            bio = io.BytesIO()
            wb.save(bio)
            bio.seek(0)
            return StreamingResponse(bio, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=unmatched_{purchase_id}.xlsx"})
        except Exception:
            # fallback a csv
            fmt = "csv"
    if fmt == "csv":
        import csv
        import io

        sio = io.StringIO()
        w = csv.writer(sio)
        w.writerow(header)
        w.writerows(rows)
        data = sio.getvalue().encode("utf-8")
        return StreamingResponse(BytesIO(data), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=unmatched_{purchase_id}.csv"})
    return JSONResponse({"detail": "formato inválido"}, status_code=400)


@router.delete("/{purchase_id}", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def delete_purchase(purchase_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    """Elimina una compra si está en estado seguro (BORRADOR o ANULADA).

    Nota: elimina también líneas y adjuntos (cascade) y borra los archivos del
    disco si existen bajo data/purchases/{id}.
    """
    # Eager-load children to support explicit delete across DBs sin cascade
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines), selectinload(Purchase.attachments))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    # In dev or when ALLOW_HARD_DELETE=true, allow deleting any status.
    allow_hard = os.getenv("ALLOW_HARD_DELETE", "0") in ("1", "true", "True")
    if not allow_hard and p.status not in ("BORRADOR", "ANULADA"):
        raise HTTPException(status_code=409, detail="Anula antes de eliminar")

    # Si se permite hard delete y la compra estaba confirmada, revertir stock
    if allow_hard and p.status == "CONFIRMADA":
        try:
            for l in list(p.lines or []):
                target = l.product_id
                if not target and l.supplier_item_id:
                    sp = await db.get(SupplierProduct, l.supplier_item_id)
                    if sp and sp.internal_product_id:
                        target = sp.internal_product_id
                if not target:
                    continue
                prod = await db.get(Product, target)
                if not prod:
                    continue
                try:
                    qty = int(Decimal(str(l.qty or 0)))
                except Exception:
                    qty = int(l.qty or 0)
                prod.stock = int(prod.stock or 0) - max(0, qty)
        except Exception:
            pass

    # Best-effort: borrar carpeta de adjuntos en disco
    try:
        root = Path("data") / "purchases" / str(p.id)
        if root.exists():
            import shutil
            shutil.rmtree(root, ignore_errors=True)
    except Exception:
        # no bloquear por problemas de archivos
        pass

    # Eliminar explícitamente hijos por compatibilidad con motores que no honran ondelete
    try:
        for l in list(p.lines or []):
            await db.delete(l)
        for a in list(p.attachments or []):
            await db.delete(a)
        await db.delete(p)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la compra: {e}")
    db.add(AuditLog(action="purchase_delete", table="purchases", entity_id=purchase_id, meta=None, user_id=(sess.user.id if sess and sess.user else None), ip=None))
    await db.commit()
    return {"status": "deleted"}


@router.get("/{purchase_id}/logs")
async def purchase_logs(purchase_id: int, db: AsyncSession = Depends(get_session), limit: int = Query(100, ge=1, le=500), format: str = Query("table")):
    stmt = (
        select(AuditLog)
        .where(AuditLog.table == "purchases", AuditLog.entity_id == purchase_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "action": r.action,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            "meta": r.meta or {},
        }
        for r in rows
    ]
    # Merge ImportLog entries if present
    try:
        il_stmt = (
            select(ImportLog)
            .where(ImportLog.purchase_id == purchase_id)
            .order_by(ImportLog.created_at.desc())
            .limit(limit)
        )
        il_rows = (await db.execute(il_stmt)).scalars().all()
        items += [
            {
                "action": f"{r.stage}:{r.event}",
                "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                "meta": {"level": r.level, **(r.details or {}), "correlation_id": r.correlation_id},
            }
            for r in il_rows
        ]
    except Exception:
        pass
    if format == "json":
        return JSONResponse(items)
    return {"items": items}


@router.get("/{purchase_id}/attachments/{attachment_id}/file")
async def download_attachment(purchase_id: int, attachment_id: int, db: AsyncSession = Depends(get_session)):
    att = await db.get(PurchaseAttachment, attachment_id)
    if not att or att.purchase_id != purchase_id:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    pth = Path(att.path)
    if not pth.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    headers = {"Content-Disposition": f"inline; filename=\"{att.filename}\""}
    return FileResponse(str(pth), media_type=att.mime or "application/octet-stream", headers=headers)
