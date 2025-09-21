# NG-HEADER: Nombre de archivo: purchases.py
# NG-HEADER: Ubicación: services/routers/purchases.py
# NG-HEADER: Descripción: Endpoints de compras (CRUD, confirmación, resend-stock, logs, importación PDF)
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
import json
import csv

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, File, UploadFile
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
from services.importers.pop_email import parse_pop_email
import httpx
import hashlib
import uuid
from agent_core.config import settings
from ai.router import AIRouter
from ai.types import Task

# PDF text extraction (opcional)
try:  # pragma: no cover - import opcional
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore

router = APIRouter(prefix="/purchases", tags=["purchases"]) 

# Helper centralizado para logging estructurado de eventos de compra
def _purchase_event_log(logger_name: str, event: str, **fields):
    import logging, json
    log = logging.getLogger(logger_name)
    try:
        flat = {k: v for k, v in fields.items() if v is not None}
        log.info("purchase_event %s %s", event, json.dumps(flat, default=str))
    except Exception:
        pass


def _extract_pdf_text(path: str, max_chars: int = 18000) -> str:
    """Extrae texto del PDF para enviar al LLM, con fallback seguro.

    - Usa pdfplumber si está disponible. Corta a max_chars.
    - Si falla, devuelve un texto indicativo o los primeros bytes hex.
    """
    try:
        if pdfplumber is not None:
            text_parts: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    try:
                        txt = page.extract_text() or ""
                    except Exception:
                        txt = ""
                    if txt:
                        text_parts.append(txt)
                    if sum(len(x) for x in text_parts) > max_chars:
                        break
            full = "\n\n".join(text_parts).strip()
            return full[:max_chars]
        # Fallback sin lib
        with open(path, "rb") as fh:
            head = fh.read(2048)
        return f"[PDF binario; primeros 2KB hex]\n{head.hex()}"
    except Exception:
        return "[No se pudo extraer texto del PDF]"


def _purchase_to_prompt_dict(p: Purchase) -> dict:
    return {
        "id": p.id,
        "supplier_id": p.supplier_id,
        "remito_number": p.remito_number,
        "remito_date": p.remito_date.isoformat() if getattr(p, "remito_date", None) else None,
        "vat_rate": float(p.vat_rate or 0),
        "lines": [
            {
                "index": idx,
                "supplier_sku": ln.supplier_sku,
                "title": ln.title,
                "qty": float(ln.qty or 0),
                "unit_cost": float(ln.unit_cost or 0),
                "line_discount": float(ln.line_discount or 0),
            }
            for idx, ln in enumerate(p.lines or [])
        ],
    }


def _format_iaval_prompt(supplier_name: str, purchase: dict, pdf_text: str) -> str:
    import json
    safe_purchase = json.dumps(purchase, ensure_ascii=False)
    # Reglas y mapeos explícitos (en español) para guiar al LLM
    rules = (
        """
Sos un validador experto de remitos. Tu objetivo es comparar el texto del remito con la compra importada
y proponer SOLO correcciones seguras. Evitá alucinar y no inventes datos. Si no estás seguro, no cambies ese campo.

Contexto del remito (frecuente):
- Encabezado suele incluir: Nombre de proveedor, Número de remito (puede figurar como "Remito", "Remito N°", "Nº Remito"), Fecha.
- Tabla de productos/servicios con columnas típicas (pueden variar en formato y orden):
    "Código", "Producto/Servicio", "Cant.", "P. Unitario", "% Bon", "P. Unitario Bonificado",
    "Subtotal", "Alic IVA", "P. Unitario C/IVA", "Total".

Mapeos a campos del sistema:
- Encabezado:
    - "Número de remito" -> header.remito_number (string)
    - "Fecha" -> header.remito_date (string ISO YYYY-MM-DD). Detectar formatos DD/MM/YYYY o YYYY-MM-DD.
    - "Alic IVA" predominante (si es consistente en todas las líneas) -> header.vat_rate (number, e.g., 0, 10.5, 21).
- Líneas (por índice existente en la compra actual):
    - "Código" -> fields.supplier_sku (string)
    - "Producto/Servicio" -> fields.title (string)
    - "Cant." -> fields.qty (number entero o decimal, normalizado con punto como separador decimal)
    - "P. Unitario" -> fields.unit_cost (number, pre-descuento). Si no existe y sólo está "P. Unitario Bonificado",
        y "% Bon" está presente, podés derivar unit_cost = unit_bonificado / (1 - %Bon/100). Si sólo tenés ambos (pre y bonificado),
        calculá fields.line_discount = (% Bon) redondeado a dos decimales; si sólo hay bonificado y no hay %Bon, no infieras.
    - "% Bon" -> fields.line_discount (number 0..100). No propagues a header.vat_rate.

Reglas estrictas de salida:
- RESPONDE EXCLUSIVAMENTE un JSON VÁLIDO con el esquema indicado, sin texto adicional, sin Markdown, sin ```.
- No agregues claves desconocidas. Sólo: header, lines, confidence, comments.
- confidence debe estar en [0,1]. comments es un array de strings cortos en español.
- Para lines, cada objeto DEBE referenciar un índice existente en la compra actual (0..N-1) y sólo proponer campos que realmente cambien.
- No modifiques product_id ni supplier_item_id. NO generes nuevas líneas.
- Números: elimina separadores de miles, usa punto como decimal (e.g., 1.234,56 -> 1234.56).
- Fechas: emitir en formato ISO YYYY-MM-DD.
- Si no hay correcciones seguras, devolvé: {"header":{},"lines":[],"confidence":0.75,"comments":["Sin diferencias evidentes"]}.

Estrategia de matching para líneas:
- Primero intenta emparejar por Código (supplier_sku) exacto.
- Si falta, usa similitud del título (Producto/Servicio) y consistencia de cantidad/precio.
- NO asignes a un índice inexistente y NO modifiques múltiples índices para la misma fila del remito.

Reglas específicas si el proveedor es POP (Distribuidora Pop):
- Los títulos de productos deben ser descriptivos: al menos 2 palabras con letras y 5 letras en total. Evitar títulos puramente numéricos.
- Ignorá o limpiá tokens como "Comprar por:x N", "Tamaño:..", o sufijos de empaque "- x N" al comparar títulos.
- Si hay pack/"x N" en el texto, no lo confundas con cantidad comprada; la cantidad suele estar en su propia columna/celda.
- Preferí títulos con mayor densidad de letras si hay dudas.

Esquema de salida EXACTO:
{
    "header": {"remito_number"?: string, "remito_date"?: string, "vat_rate"?: number},
    "lines": [ { "index": number, "fields": { "qty"?: number, "unit_cost"?: number, "line_discount"?: number, "supplier_sku"?: string, "title"?: string } } ],
    "confidence": number,
    "comments": string[]
}

Ejemplo mínimo (sólo cambios seguros):
{
    "header": {"remito_number": "0001-12345678", "remito_date": "2025-09-17", "vat_rate": 21},
    "lines": [
        {"index": 0, "fields": {"supplier_sku": "A-123", "qty": 12, "unit_cost": 1500.0, "line_discount": 10.0}},
        {"index": 2, "fields": {"title": "Maceta 12cm Negra"}}
    ],
    "confidence": 0.88,
    "comments": ["Se normaliza N° de remito y fecha", "Se corrigen SKU y % bonificación"]
}
""".strip()
    )
    # Reglas específicas POP sólo si el proveedor coincide
    extra = ""
    if (supplier_name or "").strip().lower().find("pop") != -1:
        extra = (
            "\n\nReglas específicas para POP (Distribuidora Pop):\n"
            "- Los títulos de productos deben ser descriptivos: al menos 2 palabras con letras y 5 letras en total. Evitar títulos puramente numéricos.\n"
            "- Ignorá o limpiá tokens como 'Comprar por:x N', 'Tamaño:..', o sufijos de empaque '- x N' al comparar títulos.\n"
            "- Si hay pack/'x N' en el texto, no lo confundas con cantidad comprada; la cantidad suele estar en su propia columna/celda.\n"
            "- Preferí títulos con mayor densidad de letras si hay dudas.\n"
        )
    return (
        f"Proveedor (referencia esperada): {supplier_name}\n"
        f"Compra actual (JSON):\n{safe_purchase}\n\n"
        f"Remito (texto):\n{pdf_text}\n\n"
        f"Instrucciones y mapeos:\n{rules}{extra}\n"
    )


def _strip_provider_prefix(s: str) -> str:
    for pfx in ("openai:", "ollama:"):
        if s.startswith(pfx):
            return s[len(pfx):].strip()
    return s


def _coerce_json(s: str) -> dict:
    import json
    s = _strip_provider_prefix(s)
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        s = s[i:j+1]
    return json.loads(s)


def _extract_eml_text(path: str, max_chars: int = 4000) -> str:
    """Extrae texto legible desde un archivo .eml.

    - Prefiere la parte HTML (si existe) limpiando etiquetas.
    - Si no, usa la parte text/plain.
    - Incluye el Subject al inicio si está disponible.
    - Trunca a max_chars para proteger el prompt.
    """
    try:
        import email
        from email import policy
        subject = ""
        body_html = ""
        body_text = ""
        with open(path, "rb") as fh:
            msg = email.message_from_bytes(fh.read(), policy=policy.default)
        subject = str(msg.get("Subject") or "")
        if msg.is_multipart():
            for part in msg.walk():
                ctype = (part.get_content_type() or "").lower()
                if ctype == "text/html" and not body_html:
                    body_html = part.get_content()
                elif ctype == "text/plain" and not body_text:
                    body_text = part.get_content()
        else:
            ctype = (msg.get_content_type() or "").lower()
            if ctype == "text/html":
                body_html = msg.get_content()
            else:
                body_text = msg.get_content()
        # Normalizar a texto
        txt = ""
        if body_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(body_html, "html.parser")
                txt = soup.get_text(" ")
            except Exception:
                # Fallback rápido quitando tags por regex
                import re as _re
                txt = _re.sub(r"<[^>]+>", " ", body_html)
        elif body_text:
            txt = str(body_text)
        full = (f"Subject: {subject}\n\n{txt}").strip()
        # Compactar espacios y truncar
        import re as _re
        full = _re.sub(r"\s+", " ", full).strip()
        return full[:max_chars]
    except Exception:
        return "[No se pudo extraer texto del EML]"


@router.get("/{purchase_id}/resend-info", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def purchase_resend_info(
    purchase_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Devuelve metadata mínima para UI sobre resend-stock.

    Campos:
    - status: estado actual de la compra.
    - last_resend_stock_at: timestamp ISO de último apply (o null).
    - resend_cooldown_seconds: ventana de cooldown configurada.
    - cooldown_active: bool si aún no expiró cooldown.
    - remaining_seconds: segundos restantes (si activo) redondeado hacia abajo.
    - now: timestamp actual en UTC.
    """
    res = await db.execute(select(Purchase).where(Purchase.id == purchase_id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    try:
        cooldown_seconds = int(os.getenv("PURCHASE_RESEND_COOLDOWN_SECONDS", "300"))
    except Exception:
        cooldown_seconds = 300
    last_resend = None
    meta_obj = getattr(p, "meta", {}) or {}
    if isinstance(meta_obj, dict):
        last_resend = meta_obj.get("last_resend_stock_at")
    from datetime import timedelta
    cooldown_active = False
    remaining = 0
    if last_resend:
        try:
            last_dt = datetime.fromisoformat(last_resend)
            diff = datetime.utcnow() - last_dt
            if diff < timedelta(seconds=cooldown_seconds):
                cooldown_active = True
                remaining = int((timedelta(seconds=cooldown_seconds) - diff).total_seconds())
        except Exception:
            pass
    return {
        "purchase_id": p.id,
        "status": p.status,
        "last_resend_stock_at": last_resend,
        "resend_cooldown_seconds": cooldown_seconds,
        "cooldown_active": cooldown_active,
        "remaining_seconds": remaining,
        "now": datetime.utcnow().isoformat(),
    }


def _sanitize_for_json(obj):
    """Recursively convert Decimals and datetimes to JSON-serializable types.

    Leaves other primitives intact. Used for AuditLog.meta and ImportLog.details.
    """
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        try:
            return float(obj)
        except Exception:
            return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    # basic types (int, float, str, bool)
    return obj


def _normalize_title_for_dedupe(x: str) -> str:
    t = (x or "").strip().lower()
    try:
        import unicodedata
        t = ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))
    except Exception:
        pass
    return ' '.join(t.split())


def _dedupe_lines(lines: list[dict]) -> tuple[list[dict], int, int]:
    """Filtra líneas duplicadas por SKU y por título normalizado.

    Devuelve (unique_lines, ignored_by_sku, ignored_by_title).
    """
    seen_skus: set[str] = set()
    seen_titles: set[str] = set()
    unique_lines: list[dict] = []
    ignored_by_sku = 0
    ignored_by_title = 0
    for ln in lines:
        sku_key = (ln.get("supplier_sku") or "").strip().lower()
        title_key = _normalize_title_for_dedupe((ln.get("title") or ""))
        if sku_key:
            if sku_key in seen_skus:
                ignored_by_sku += 1
                continue
            seen_skus.add(sku_key)
        if title_key:
            if title_key in seen_titles:
                ignored_by_title += 1
                continue
            seen_titles.add(title_key)
        unique_lines.append(ln)
    return unique_lines, ignored_by_sku, ignored_by_title


@router.post("", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def create_purchase(payload: dict, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    """Crea una compra en estado BORRADOR.

    Requiere: supplier_id, remito_number, remito_date (ISO).
    Devuelve: { id, status }.
    Unicidad por (supplier_id, remito_number).
    """
    supplier_id = payload.get("supplier_id")
    remito_number = payload.get("remito_number")
    remito_date = payload.get("remito_date")
    if not supplier_id or not remito_number or not remito_date:
        raise HTTPException(status_code=400, detail="supplier_id, remito_number y remito_date son obligatorios")
    # Validar y normalizar fecha del remito (ISO YYYY-MM-DD)
    try:
        remito_dt = date.fromisoformat(remito_date)
    except Exception:
        raise HTTPException(status_code=400, detail="remito_date inválida, formato esperado YYYY-MM-DD")
    # Unicidad por (supplier_id, remito_number)
    exists = await db.scalar(select(Purchase).where(Purchase.supplier_id==supplier_id, Purchase.remito_number==remito_number))
    if exists:
        # Alinear con política general: 409 cuando ya existe (tests lo esperan)
        raise HTTPException(status_code=409, detail="Compra ya existe para ese proveedor y remito")
    p = Purchase(
        supplier_id=supplier_id,
        remito_number=remito_number,
        remito_date=remito_dt,
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
    """Actualiza encabezado y líneas de una compra.

    - Encabezado: global_discount, vat_rate, note, remito_date, depot_id, remito_number.
    - Líneas: upsert/delete con `lines` [{ id?, op=upsert|delete, ... }].
    """
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
    """Lista compras con filtros y paginación.

    Filtros: supplier_id, status, depot_id, remito_number, product_name, date_from, date_to.
    Paginación: page, page_size.
    """
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
    """Obtiene una compra con totales, líneas y adjuntos.

    Calcula subtotal, iva y total a partir de líneas y vat_rate.
    """
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
    """Valida líneas y estado de la compra.

    Marca cada línea como OK o SIN_VINCULAR según vínculos.
    Estado: VALIDADA si todas las líneas están resueltas y hay al menos una; caso contrario BORRADOR.
    """
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
    auto_linked = 0
    missing_skus: set[str] = set()
    # Intentar auto-vincular por supplier_sku cuando falte vínculo
    for l in p.lines:
        try:
            linked = bool(l.product_id or l.supplier_item_id)
            if not linked:
                sku_txt = (l.supplier_sku or "").strip()
                if sku_txt:
                    try:
                        sp = await db.scalar(
                            select(SupplierProduct).where(
                                SupplierProduct.supplier_id == p.supplier_id,
                                SupplierProduct.supplier_product_id == sku_txt,
                            )
                        )
                    except Exception:
                        sp = None
                    if sp:
                        l.supplier_item_id = sp.id
                        if not l.product_id and getattr(sp, "internal_product_id", None):
                            l.product_id = sp.internal_product_id
                        auto_linked += 1
                        linked = True
                    else:
                        missing_skus.add(sku_txt)
            # Marcar estado según resultado final
            linked = bool(l.product_id or l.supplier_item_id)
            l.state = "OK" if linked else "SIN_VINCULAR"
            if not linked:
                unmatched += 1
        except Exception:
            # En caso de error silencioso, mantener estado previo y contar como sin vincular si aplica
            linked = bool(l.product_id or l.supplier_item_id)
            l.state = "OK" if linked else "SIN_VINCULAR"
            if not linked:
                unmatched += 1
    # Requiere al menos 1 línea para quedar VALIDADA
    p.status = "VALIDADA" if (unmatched == 0 and total_lines > 0) else "BORRADOR"
    await db.commit()
    return {
        "status": "ok",
        "unmatched": unmatched,
        "lines": total_lines,
        "linked": auto_linked,
        "missing_skus": sorted(missing_skus) if missing_skus else [],
    }


@router.post("/{purchase_id}/iaval/preview", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def iaval_preview(purchase_id: int, db: AsyncSession = Depends(get_session)):
    """Genera una propuesta de correcciones con IA, sin aplicar cambios.

    Requiere que la compra esté en BORRADOR y tenga un PDF adjunto.
    Devuelve la propuesta cruda, un diff amigable, confianza y comentarios.
    """
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines), selectinload(Purchase.attachments), selectinload(Purchase.supplier))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status != "BORRADOR":
        raise HTTPException(status_code=400, detail="Solo disponible en BORRADOR")
    if not p.attachments:
        raise HTTPException(status_code=400, detail="La compra no tiene documento adjunto (PDF o EML)")
    # Preferir PDF si existe, si no intentar EML/texto
    pdf_text = None
    att_pdf = None
    att_eml = None
    for att in p.attachments:
        mime = (att.mime or "").lower()
        name = (att.filename or "").lower()
        if (mime.startswith("application/pdf") or name.endswith(".pdf")) and os.path.exists(att.path):
            att_pdf = att
            break
        if (mime in {"message/rfc822", "application/eml", "text/html", "text/plain", "application/octet-stream"} or name.endswith(".eml")) and os.path.exists(att.path):
            att_eml = att if att_eml is None else att_eml
    if att_pdf:
        pdf_text = _extract_pdf_text(att_pdf.path)
    elif att_eml:
        pdf_text = _extract_eml_text(att_eml.path)
    else:
        raise HTTPException(status_code=400, detail="No se encontró adjunto legible (PDF o EML)")
    purchase_json = _purchase_to_prompt_dict(p)
    supplier_name = getattr(getattr(p, "supplier", None), "name", None) or f"Proveedor {p.supplier_id}"
    prompt = _format_iaval_prompt(supplier_name, purchase_json, pdf_text)
    router_ai = AIRouter(settings)
    raw = router_ai.run(Task.REASONING.value, prompt)
    parsed = None
    try:
        parsed = _coerce_json(raw)
    except Exception:
        # Estrategia amable: si el proveedor devolvió texto no JSON, preferimos degradar
        # a una propuesta vacía en lugar de 502 para no bloquear el flujo.
        # Intento adicional: detectar bloque ```json ... ``` y extraer.
        try:
            s = raw or ""
            start = s.find("```json")
            if start != -1:
                start = s.find("{", start)
                end = s.rfind("}")
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(s[start:end+1])
        except Exception:
            parsed = None
        if parsed is None:
            # Devolver respuesta neutra con comentarios diagnósticos
            return {
                "proposal": {"header": {}, "lines": []},
                "diff": {"header": {}, "lines": []},
                "confidence": 0.0,
                "comments": [
                    "El proveedor IA no devolvió JSON válido. Mostramos resultado vacío.",
                    "Sugerencia: revisar configuración de IA (OPENAI_API_KEY, Ollama) o reintentar."
                ],
                "raw": raw,
            }
    header = parsed.get("header") or {}
    lines = parsed.get("lines") or []
    confidence = parsed.get("confidence") or 0
    comments = parsed.get("comments") or []
    # Construir diff
    diff = {"header": {}, "lines": []}
    if isinstance(header, dict):
        # remito_number, remito_date, vat_rate
        if "remito_number" in header and header["remito_number"] is not None and str(header["remito_number"]) != str(p.remito_number):
            diff["header"]["remito_number"] = {"old": p.remito_number, "new": header["remito_number"]}
        if "remito_date" in header and header["remito_date"]:
            try:
                nd = date.fromisoformat(str(header["remito_date"]))
                if getattr(p, "remito_date", None) != nd:
                    diff["header"]["remito_date"] = {"old": p.remito_date.isoformat() if getattr(p, "remito_date", None) else None, "new": nd.isoformat()}
            except Exception:
                pass
        if "vat_rate" in header and header["vat_rate"] is not None:
            try:
                if float(p.vat_rate or 0) != float(header["vat_rate"]):
                    diff["header"]["vat_rate"] = {"old": float(p.vat_rate or 0), "new": float(header["vat_rate"])}
            except Exception:
                pass
    if isinstance(lines, list):
        for item in lines:
            try:
                idx = int(item.get("index"))
                fields = item.get("fields") or {}
            except Exception:
                continue
            if idx < 0 or idx >= len(p.lines):
                continue
            ln = p.lines[idx]
            chg = {}
            for f in ("qty", "unit_cost", "line_discount"):
                if f in fields and fields[f] is not None:
                    try:
                        ov = float(getattr(ln, f) or 0)
                        nv = float(fields[f])
                        if ov != nv:
                            chg[f] = {"old": ov, "new": nv}
                    except Exception:
                        pass
            for f in ("supplier_sku", "title"):
                if f in fields and fields[f] is not None and str(getattr(ln, f) or "") != str(fields[f]):
                    chg[f] = {"old": getattr(ln, f), "new": fields[f]}
            if chg:
                diff["lines"].append({"index": idx, "changes": chg})
    return {"proposal": {"header": header, "lines": lines}, "diff": diff, "confidence": confidence, "comments": comments, "raw": raw}


@router.post("/{purchase_id}/iaval/apply", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def iaval_apply(
    purchase_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_session),
    emit_log: int = Query(0),
):
    """Aplica una propuesta de iAVaL a la compra en BORRADOR.

    Cambios permitidos:
    - Header: remito_number, remito_date, vat_rate
    - Líneas: qty, unit_cost, line_discount, supplier_sku, title (por índice)
    """
    res = await db.execute(select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status != "BORRADOR":
        raise HTTPException(status_code=400, detail="Solo disponible en BORRADOR")
    prop = payload.get("proposal") or {}
    header = prop.get("header") or {}
    lines = prop.get("lines") or []
    applied = {"header": {}, "lines": []}
    # Header
    if "remito_number" in header and header["remito_number"]:
        if str(p.remito_number) != str(header["remito_number"]):
            applied["header"]["remito_number"] = {"old": p.remito_number, "new": header["remito_number"]}
            p.remito_number = str(header["remito_number"])  
    if "remito_date" in header and header["remito_date"]:
        try:
            nd = date.fromisoformat(str(header["remito_date"]))
            if getattr(p, "remito_date", None) != nd:
                applied["header"]["remito_date"] = {"old": p.remito_date.isoformat() if getattr(p, "remito_date", None) else None, "new": nd.isoformat()}
                p.remito_date = nd
        except Exception:
            pass
    if "vat_rate" in header and header["vat_rate"] is not None:
        try:
            nv = float(header["vat_rate"])  # noqa: F841
            if float(p.vat_rate or 0) != float(header["vat_rate"]):
                applied["header"]["vat_rate"] = {"old": float(p.vat_rate or 0), "new": float(header["vat_rate"])}
                p.vat_rate = header["vat_rate"]
        except Exception:
            pass
    # Lines
    if isinstance(lines, list):
        for item in lines:
            try:
                idx = int(item.get("index"))
                fields = item.get("fields") or {}
            except Exception:
                continue
            if idx < 0 or idx >= len(p.lines):
                continue
            ln = p.lines[idx]
            chg = {}
            if "qty" in fields and fields["qty"] is not None:
                try:
                    if float(ln.qty or 0) != float(fields["qty"]):
                        chg["qty"] = {"old": float(ln.qty or 0), "new": float(fields["qty"])}
                        ln.qty = fields["qty"]
                except Exception:
                    pass
            if "unit_cost" in fields and fields["unit_cost"] is not None:
                try:
                    if float(ln.unit_cost or 0) != float(fields["unit_cost"]):
                        chg["unit_cost"] = {"old": float(ln.unit_cost or 0), "new": float(fields["unit_cost"])}
                        ln.unit_cost = fields["unit_cost"]
                except Exception:
                    pass
            if "line_discount" in fields and fields["line_discount"] is not None:
                try:
                    if float(ln.line_discount or 0) != float(fields["line_discount"]):
                        chg["line_discount"] = {"old": float(ln.line_discount or 0), "new": float(fields["line_discount"])}
                        ln.line_discount = fields["line_discount"]
                except Exception:
                    pass
            if "supplier_sku" in fields and fields["supplier_sku"] is not None:
                if (ln.supplier_sku or "") != str(fields["supplier_sku"]):
                    chg["supplier_sku"] = {"old": ln.supplier_sku, "new": str(fields["supplier_sku"])}
                    ln.supplier_sku = str(fields["supplier_sku"]) or None
            if "title" in fields and fields["title"] is not None:
                if (ln.title or "") != str(fields["title"]):
                    chg["title"] = {"old": ln.title, "new": str(fields["title"])}
                    ln.title = str(fields["title"]) or ln.title
            if chg:
                applied["lines"].append({"index": idx, "changes": chg})
    db.add(AuditLog(action="purchase.iaval.apply", table="purchases", entity_id=p.id, meta={"applied": applied}))

    log_info = None
    if emit_log:
        # Generar archivo con timestamp y metadatos del remito y diff aplicado
        try:
            from datetime import datetime as _dt
            ts = _dt.utcnow().strftime("%Y%m%d_%H%M%S")
            root = Path("data") / "purchases" / str(p.id) / "logs"
            root.mkdir(parents=True, exist_ok=True)
            fname_json = f"iaval_changes_{ts}.json"
            fpath_json = root / fname_json
            meta = {
                "timestamp_iso": _dt.utcnow().isoformat() + "Z",
                "purchase_id": p.id,
                "supplier_id": p.supplier_id,
                "remito_number": p.remito_number,
                "remito_date": (p.remito_date.isoformat() if getattr(p, "remito_date", None) else None),
                "diff": applied,
                "source": "iaval",
            }
            with open(fpath_json, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2)

            # Generar CSV con filas (type, index, field, old, new)
            fname_csv = f"iaval_changes_{ts}.csv"
            fpath_csv = root / fname_csv
            try:
                with open(fpath_csv, "w", encoding="utf-8", newline="") as fhc:
                    writer = csv.writer(fhc)
                    writer.writerow(["type", "index", "field", "old", "new"])
                    # Header changes
                    for fld, chg in (applied.get("header") or {}).items():
                        writer.writerow(["header", "", fld, chg.get("old"), chg.get("new")])
                    # Line changes
                    for item in (applied.get("lines") or []):
                        idx = item.get("index")
                        for fld, chg in (item.get("changes") or {}).items():
                            writer.writerow(["line", idx, fld, chg.get("old"), chg.get("new")])
            except Exception:
                # Si falla CSV, continuar con JSON
                fname_csv = None
                fpath_csv = None

            # Info de log incluyendo URLs de descarga relativas
            log_info = {
                "filename": fname_json,
                "path": str(fpath_json),
                "csv_filename": fname_csv,
                "url_json": f"/purchases/{p.id}/logs/files/{fname_json}",
                "url_csv": (f"/purchases/{p.id}/logs/files/{fname_csv}" if fname_csv else None),
            }
            db.add(AuditLog(action="purchase.iaval.emit_change_log", table="purchases", entity_id=p.id, meta={"file": str(fpath_json), "size": fpath_json.stat().st_size, "csv": (str(fpath_csv) if fpath_csv else None)}))
        except Exception as _e:
            # No bloquear apply; registrar error no bloqueante
            try:
                db.add(AuditLog(action="purchase.iaval.emit_change_log_error", table="purchases", entity_id=p.id, meta={"error": str(_e)}))
            except Exception:
                pass

    await db.commit()
    resp = {"ok": True, "applied": applied}
    if log_info:
        resp["log"] = log_info
    return resp


@router.post("/{purchase_id}/confirm", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def confirm_purchase(
    purchase_id: int,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    debug: int = Query(0),
):
    """Confirma la compra e impacta stock y precios.

    - Aumenta stock por producto vinculado (product_id o supplier_item_id -> internal_product_id).
    - Actualiza current_purchase_price en SupplierProduct y registra PriceHistory.
    - Deja AuditLog con resumen y deltas; notifica por Telegram si está configurado.
    - Si PURCHASE_CONFIRM_REQUIRE_ALL_LINES=1 y hay líneas sin resolver, aborta con 422 y revierte.
    """
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status == "CONFIRMADA":
        return {"status": "ok", "already_confirmed": True}

    now = datetime.utcnow()
    # Impactar stock y buy_price + price_history (deduplicado por SupplierProduct)
    applied_deltas: list[dict[str, int | None]] = []
    import logging
    log = logging.getLogger("growen")
    unresolved: list[int] = []

    # Seguimiento de updates por SupplierProduct para evitar PriceHistory duplicado
    sp_updates: dict[int, dict[str, Any]] = {}

    for l in p.lines:
            # Ajuste de costo por descuentos
            ln_disc = Decimal(str(l.line_discount or 0)) / Decimal("100")
            unit_cost = Decimal(str(l.unit_cost or 0))
            eff = unit_cost * (Decimal("1") - ln_disc)

            # Resolver supplier_item_id por SKU si falta (autovínculo en confirmación)
            sp = None
            if not l.supplier_item_id:
                sku_txt = (l.supplier_sku or "").strip()
                if sku_txt:
                    try:
                        sp = await db.scalar(
                            select(SupplierProduct).where(
                                SupplierProduct.supplier_id == p.supplier_id,
                                SupplierProduct.supplier_product_id == sku_txt,
                            )
                        )
                    except Exception:
                        sp = None
                    if sp:
                        # Completar vínculo en la línea para persistirlo al commit
                        l.supplier_item_id = sp.id
                        # Si el SupplierProduct ya conoce el producto interno, usarlo
                        if not l.product_id and sp.internal_product_id:
                            l.product_id = sp.internal_product_id

            # Determinar SupplierProduct para registrar precio efectivo
            if l.supplier_item_id and not sp:
                sp = await db.get(SupplierProduct, l.supplier_item_id)
            if sp:
                sp_id = sp.id
                # Capturar old price solo la primera vez
                if sp_id not in sp_updates:
                    try:
                        old_val = Decimal(str(sp.current_purchase_price or 0))
                    except Exception:
                        old_val = Decimal("0")
                    sp_updates[sp_id] = {"sp": sp, "old": old_val, "new": eff}
                else:
                    sp_updates[sp_id]["new"] = eff  # última observación gana

            # Impacto en stock a nivel producto
            prod_id: Optional[int] = l.product_id
            if not prod_id and l.supplier_item_id:
                sp2 = sp if sp and sp.id == l.supplier_item_id else await db.get(SupplierProduct, l.supplier_item_id)
                if sp2 and sp2.internal_product_id:
                    prod_id = sp2.internal_product_id
            if prod_id:
                # Obtener producto. with_for_update es ignorado por SQLite y efectivo en Postgres.
                try:
                    pr = await db.execute(select(Product).where(Product.id == prod_id).with_for_update())
                    prod = pr.scalar_one_or_none()
                except Exception:
                    prod = await db.get(Product, prod_id)
                if prod:
                    try:
                        qty = int(Decimal(str(l.qty or 0)))
                    except Exception:
                        qty = int(l.qty or 0)
                    old_stock = int(prod.stock or 0)
                    inc = max(0, qty)
                    prod.stock = old_stock + inc
                    applied_deltas.append({
                        "product_id": prod.id,
                        "product_title": getattr(prod, "title", None),
                        "old": old_stock,
                        "delta": inc,
                        "new": prod.stock,
                        "line_id": l.id,
                    })
                    try:
                        log.info(
                            "purchase_confirm: purchase=%s line=%s product=%s old_stock=%s +%s -> new_stock=%s",
                            p.id, l.id, prod.id, old_stock, inc, prod.stock
                        )
                    except Exception:
                        pass
                else:
                    unresolved.append(l.id)
            else:
                unresolved.append(l.id)

    # Si hay líneas sin resolver y la política estricta está activa, abortar antes de confirmar
    try:
        require_all = os.getenv("PURCHASE_CONFIRM_REQUIRE_ALL_LINES", "0") in ("1", "true", "True")
    except Exception:
        require_all = False
    if unresolved and require_all:
        # Revertir cambios no comprometidos
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unresolved_lines",
                "message": "Existen líneas sin producto vinculado; corregí antes de confirmar",
                "unresolved_line_ids": unresolved,
            },
        )

    # Aplicar cambios de precio una sola vez por SupplierProduct y registrar PriceHistory
    for sp_id, info in sp_updates.items():
        sp_obj: SupplierProduct = info["sp"]
        old = info["old"]
        new = info["new"]
        sp_obj.current_purchase_price = new
        if getattr(sp_obj, "current_sale_price", None) is None:
            sp_obj.current_sale_price = new
            try:
                log.info("purchase_confirm default_sale_applied sp=%s eff=%s", sp_obj.id, str(new))
            except Exception:
                pass
        ph = PriceHistory(
            entity_type="supplier",
            entity_id=sp_obj.id,
            price_old=old,
            price_new=new,
            note=f"Compra #{p.id} remito {p.remito_number}",
            user_id=sess.user.id if sess.user else None,
            ip=None,
        )
        db.add(ph)

    # Calcular totales para auditoría y verificación
    def _to_dec(x) -> Decimal:
        try:
            return Decimal(str(x or 0))
        except Exception:
            return Decimal("0")

    subtotal_all = Decimal("0")
    subtotal_applied = Decimal("0")
    for l in p.lines:
        qty = _to_dec(l.qty)
        u = _to_dec(l.unit_cost)
        disc = _to_dec(l.line_discount)
        eff_unit = u * (Decimal("1") - (disc / Decimal("100")))
        line_total = (eff_unit * qty)
        subtotal_all += line_total
    # applied_deltas ya tiene sólo las líneas que impactaron stock (product_id resoluble)
    applied_line_ids = {d.get("line_id") for d in applied_deltas if d.get("line_id")}
    for l in p.lines:
        if l.id in applied_line_ids:
            qty = _to_dec(l.qty)
            u = _to_dec(l.unit_cost)
            disc = _to_dec(l.line_discount)
            eff_unit = u * (Decimal("1") - (disc / Decimal("100")))
            subtotal_applied += (eff_unit * qty)

    gd = _to_dec(p.global_discount)
    vr = _to_dec(p.vat_rate)
    discount_factor = (Decimal("1") - (gd / Decimal("100")))
    vat_factor = (Decimal("1") + (vr / Decimal("100"))) if vr > 0 else Decimal("1")
    try:
        purchase_total = (subtotal_all * discount_factor * vat_factor).quantize(Decimal("0.01"))
        applied_total = (subtotal_applied * discount_factor * vat_factor).quantize(Decimal("0.01"))
    except Exception:
        purchase_total = subtotal_all
        applied_total = subtotal_applied
    diff = (purchase_total - applied_total).copy_abs()
    # Tolerancia configurable (porcentaje del total de compra)
    try:
        tol_pct = Decimal(os.getenv("PURCHASE_TOTAL_MISMATCH_TOLERANCE_PCT", "0.005"))  # 0.5%
    except Exception:
        tol_pct = Decimal("0.005")
    reference = purchase_total if purchase_total > 0 else Decimal("1")
    tol_abs = (reference * tol_pct).quantize(Decimal("0.01"))
    mismatch = diff > tol_abs

    # Marcar compra como confirmada
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
            sp3 = await db.get(SupplierProduct, l.supplier_item_id)
            if sp3 and sp3.internal_product_id:
                target = sp3.internal_product_id
        if target:
            stock_deltas.append({"product_id": target, "delta": int(max(0, q))})
    # Si hay líneas sin producto resoluble, las dejamos registradas en meta para diagnóstico
    db.add(
        AuditLog(
            action="purchase_confirm",
            table="purchases",
            entity_id=p.id,
            meta={
                "lines": len(p.lines),
                "stock_deltas": stock_deltas,
                "applied_deltas": applied_deltas if debug else None,
                "unresolved_lines": unresolved or None,
                "totals": {
                    "subtotal_all": str(subtotal_all),
                    "subtotal_applied": str(subtotal_applied),
                    "discount_factor": str(discount_factor),
                    "vat_factor": str(vat_factor),
                    "purchase_total": str(purchase_total),
                    "applied_total": str(applied_total),
                    "diff": str(diff),
                    "tolerance_abs": str(tol_abs),
                    "tolerance_pct": str(tol_pct),
                    "mismatch": bool(mismatch),
                },
            },
            user_id=sess.user.id if sess.user else None,
            ip=None,
        )
    )
    # Confirmar transacción de cambios (stock, precios, estado y auditoría)
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
    resp: dict[str, Any] = {"status": "ok"}
    if debug:
        resp["applied_deltas"] = applied_deltas
        resp["unresolved_lines"] = unresolved or []
    # Adjuntar verificación de totales siempre
    resp["totals"] = {
        "purchase_total": float(purchase_total),
        "applied_total": float(applied_total),
        "diff": float(diff),
        "tolerance_abs": float(tol_abs),
        "tolerance_pct": float(tol_pct),
        "mismatch": bool(mismatch),
    }
    # Si hay mismatch significativo, exponer que puede hacer rollback
    if mismatch:
        resp["can_rollback"] = True
        resp["hint"] = "Los totales de la compra y de los productos impactados difieren; puede ejecutar rollback."
    return resp


@router.post("/{purchase_id}/resend-stock", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def resend_stock(
    purchase_id: int,
    db: AsyncSession = Depends(get_session),
    sess: SessionData = Depends(current_session),
    apply: int = Query(0, description="Si =1 aplica cambios; si =0 sólo preview"),
    debug: int = Query(0),
):
    """Re-aplica (o previsualiza) los impactos de stock de una compra previamente CONFIRMADA.

    Casos de uso: reparar stock tras rollback parcial, auditoría o si se detectó que algún listener externo falló.

    Reglas:
    - Sólo permitido si la compra está CONFIRMADA.
    - Calcula deltas como en confirm_purchase (qty de líneas con vínculo resoluble).
    - Si `apply=0` devuelve previsualización (no cambia stock).
    - Si `apply=1` suma nuevamente las cantidades al stock actual.
    - Registra AuditLog (action="purchase_resend_stock").
    - Opcional debug para devolver applied_deltas detallados.
    - No modifica estado de la compra.
    - No re-escribe precios de compra (price history) para evitar distorsión histórica.
    """
    res = await db.execute(
        select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status != "CONFIRMADA":
        raise HTTPException(status_code=400, detail="Sólo se puede reenviar stock de una compra CONFIRMADA")

    # Cooldown (evitar doble aplicación accidental)
    from datetime import timedelta
    try:
        cooldown_seconds = int(os.getenv("PURCHASE_RESEND_COOLDOWN_SECONDS", "300"))
    except Exception:
        cooldown_seconds = 300
    if apply:
        meta_obj = getattr(p, "meta", {}) or {}
        last_ts = meta_obj.get("last_resend_stock_at") if isinstance(meta_obj, dict) else None
        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts)
                if datetime.utcnow() - last_dt < timedelta(seconds=cooldown_seconds):
                    raise HTTPException(status_code=429, detail="Cooldown activo: esperá antes de reenviar stock nuevamente")
            except HTTPException:
                raise
            except Exception:
                pass

    # Recalcular deltas de stock resolubles
    applied_deltas: list[dict[str, int | None]] = []
    unresolved: list[int] = []
    import logging, os as _os
    log = logging.getLogger("growen")
    for l in p.lines:
        prod_id: Optional[int] = l.product_id
        if not prod_id and l.supplier_item_id:
            sp = await db.get(SupplierProduct, l.supplier_item_id)
            if sp and sp.internal_product_id:
                prod_id = sp.internal_product_id
        # Intentar resolver por SKU si aún no hay vínculo
        if not prod_id and not l.supplier_item_id and (l.supplier_sku or "").strip():
            try:
                sp = await db.scalar(
                    select(SupplierProduct).where(
                        SupplierProduct.supplier_id == p.supplier_id,
                        SupplierProduct.supplier_product_id == (l.supplier_sku or "").strip(),
                    )
                )
                if sp and sp.internal_product_id:
                    prod_id = sp.internal_product_id
                    # Opcional: completar vínculos en línea para futuras consultas
                    l.supplier_item_id = sp.id
                    l.product_id = prod_id
            except Exception:
                pass
        if not prod_id:
            unresolved.append(l.id)
            continue
        try:
            qty = int(Decimal(str(l.qty or 0)))
        except Exception:
            qty = int(l.qty or 0)
        inc = max(0, qty)
        prod = await db.get(Product, prod_id)
        if not prod:
            unresolved.append(l.id)
            continue
        old_stock = int(prod.stock or 0)
        new_stock = old_stock + inc if apply else old_stock
        applied_deltas.append({
            "product_id": prod.id,
            "product_title": getattr(prod, "title", None),
            "old": old_stock,
            "delta": inc,
            "new": new_stock if apply else old_stock + inc,  # expected new
            "line_id": l.id,
        })
        if apply:
            prod.stock = new_stock
        try:
            log.info(
                "purchase_resend_stock: purchase=%s line=%s product=%s apply=%s old_stock=%s +%s -> %s",
                p.id, l.id, prod.id, bool(apply), old_stock, inc, new_stock if apply else old_stock + inc
            )
        except Exception:
            pass

    if apply:
        db.add(
            AuditLog(
                action="purchase_resend_stock",
                table="purchases",
                entity_id=p.id,
                meta={
                    "lines": len(p.lines),
                    "applied": True,
                    "deltas": applied_deltas if debug else None,
                    "unresolved_lines": unresolved or None,
                    "cooldown_seconds": cooldown_seconds,
                },
                user_id=sess.user.id if sess and sess.user else None,
                ip=None,
            )
        )
        # Persistir timestamp en meta de purchase
        try:
            pm = getattr(p, "meta", {}) or {}
            if isinstance(pm, dict):
                pm["last_resend_stock_at"] = datetime.utcnow().isoformat()
                setattr(p, "meta", pm)
        except Exception:
            pass
        await db.commit()
    else:
        # Preview (sin commit) — sólo log de auditoría en memoria si se desea
        try:
            db.add(
                AuditLog(
                    action="purchase_resend_stock_preview",
                    table="purchases",
                    entity_id=p.id,
                    meta={
                        "lines": len(p.lines),
                        "applied": False,
                        "deltas": applied_deltas if debug else None,
                        "unresolved_lines": unresolved or None,
                    },
                    user_id=sess.user.id if sess and sess.user else None,
                    ip=None,
                )
            )
            await db.commit()
        except Exception:
            pass

    _purchase_event_log("growen", "resend_stock", purchase_id=p.id, mode="apply" if apply else "preview", lines=len(p.lines), unresolved=len(unresolved), applied=bool(apply))
    return {
        "status": "ok",
        "mode": "apply" if apply else "preview",
        "applied_deltas": applied_deltas if debug else None,
        "unresolved_lines": unresolved or None,
    }


@router.post("/{purchase_id}/cancel", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def cancel_purchase(purchase_id: int, payload: dict, db: AsyncSession = Depends(get_session)):
    """Anula una compra y revierte stock si estaba confirmada.

    Requiere note. Registra AuditLog con detalle.
    """
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


@router.post("/{purchase_id}/rollback", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def rollback_purchase(purchase_id: int, db: AsyncSession = Depends(get_session), sess: SessionData = Depends(current_session)):
    """Revierte el impacto de stock de una compra CONFIRMADA y la marca ANULADA.

    - No requiere `note`.
    - Registra AuditLog con detalle de productos revertidos.
    - Si la compra no está CONFIRMADA, responde 400.
    """
    res = await db.execute(
        select(Purchase).options(selectinload(Purchase.lines)).where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status != "CONFIRMADA":
        raise HTTPException(status_code=400, detail="Sólo se puede aplicar rollback a una compra CONFIRMADA")

    reverted = []
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
    db.add(
        AuditLog(
            action="purchase_rollback",
            table="purchases",
            entity_id=p.id,
            meta={"reverted": reverted},
            user_id=sess.user.id if sess.user else None,
            ip=None,
        )
    )
    await db.commit()
    return {"status": "ok", "reverted": reverted}


@router.post("/import/santaplanta", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def import_santaplanta_pdf(
    supplier_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    debug: int = Query(0),
    force_ocr: int = Query(0),
):
    """Importa PDF de Santa Planta mediante pipeline.

    Guarda temporal, ejecuta parse_remito (pdfplumber → camelot → OCR),
    deduplica por (supplier_id, remito_number) y hash, crea compra, adjunta PDF
    y genera líneas con matching (SKU y fuzzy por título). Si debug está activo,
    devuelve eventos y muestras.
    """
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
        # --- Fallback IA (fase 2: no líneas O baja confianza) ---
        try:
            from agent_core.config import settings as _st
            low_conf = False
            if res.lines and hasattr(res, 'classic_confidence'):
                try:
                    low_conf = res.classic_confidence < _st.import_ai_classic_min_confidence
                except Exception:
                    low_conf = False
            if (not res.lines or low_conf) and _st.import_ai_enabled:
                from services.importers.ai_fallback import run_ai_fallback, merge_ai_lines
                text_excerpt = (getattr(res, 'text_excerpt', None) or getattr(res, 'debug', {}).get('text_excerpt') or "")
                ai_result = run_ai_fallback(
                    correlation_id=correlation_id,
                    text_excerpt=text_excerpt,
                    classic_lines_hint=len(res.lines or []),
                    classic_confidence=getattr(res, 'classic_confidence', None),
                )
                # Añadir eventos AI al final
                for ev in ai_result.events:
                    res.events.append(ev)
                if ai_result.ok and ai_result.payload:
                    merged, stats = merge_ai_lines(res.lines or [], ai_result.payload, _st.import_ai_min_confidence)
                    res.lines = merged
                    res.events.append({"level": "INFO", "stage": "ai", "event": "merged", "details": stats})
                else:
                    res.events.append({"level": "INFO", "stage": "ai", "event": "no_data", "details": {"reason": ai_result.error}})
        except Exception as _ai_e:  # No debe abortar importación
            try:
                res.events.append({"level": "WARN", "stage": "ai", "event": "exception", "details": {"error": str(_ai_e)}})
            except Exception:
                pass
        log.info(f"Import[{correlation_id}]: Pipeline finalizado. Remito={res.remito_number}, Fecha={res.remito_date}, Líneas detectadas={len(res.lines) if res.lines else 0}")

        remito_number = res.remito_number or file.filename
        remito_date_str = res.remito_date
        try:
            remito_dt = date.fromisoformat(remito_date_str) if remito_date_str else date.today()
        except Exception:
            remito_dt = date.today()

    # --- Política de BORRADOR vacío ---
        # Política configurable en caliente vía env var (fallback al valor de Settings)
        if "IMPORT_ALLOW_EMPTY_DRAFT" in os.environ:
            ALLOW_EMPTY = str(os.getenv("IMPORT_ALLOW_EMPTY_DRAFT", "true")).lower() == "true"
        else:
            ALLOW_EMPTY = settings.import_allow_empty_draft
        if not res.lines:
            if ALLOW_EMPTY:
                # Pre-chequeo de duplicados por (proveedor, remito)
                exists = await db.scalar(
                    select(Purchase).where(
                        Purchase.supplier_id == supplier_id,
                        Purchase.remito_number == remito_number,
                    )
                )
                if exists:
                    raise HTTPException(status_code=409, detail="Compra ya existe para ese proveedor y remito")
                # Pre-chequeo de duplicado por hash del PDF para el mismo proveedor
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
                # Crear compra vacía (BORRADOR), adjuntar PDF y devolver 200
                p = Purchase(supplier_id=supplier_id, remito_number=remito_number, remito_date=remito_dt)
                db.add(p)
                await db.flush()
                root = Path("data") / "purchases" / str(p.id)
                root.mkdir(parents=True, exist_ok=True)
                pdf_path = root / file.filename
                with open(pdf_path, "wb") as fh:
                    fh.write(content)
                db.add(PurchaseAttachment(purchase_id=p.id, filename=file.filename, mime=file.content_type, size=len(content), path=str(pdf_path)))
                try:
                    samples_empty = (res.debug.get("samples") if isinstance(res.debug, dict) else None)
                except Exception:
                    samples_empty = None
                meta_obj = {
                    "correlation_id": correlation_id,
                    "filename": file.filename,
                    "sha256": sha256,
                    "remito_number": remito_number,
                    "remito_date": remito_dt.isoformat(),
                    "lines_detected": 0,
                    "note": "empty_draft_allowed",
                    "samples": samples_empty,
                }
                db.add(AuditLog(action="purchase_import", table="purchases", entity_id=p.id, meta=_sanitize_for_json(meta_obj)))
                # Registrar eventos del pipeline en ImportLog para diagnóstico aunque no haya líneas
                try:
                    for ev in (res.events or []):
                        try:
                            details = ev.get("details") or {}
                        except Exception:
                            details = {}
                        db.add(
                            ImportLog(
                                purchase_id=p.id,
                                correlation_id=correlation_id,
                                level=str(ev.get("level") or "INFO"),
                                stage=str(ev.get("stage") or ""),
                                event=str(ev.get("event") or ""),
                                details=_sanitize_for_json(details),
                            )
                        )
                    # Registrar métrica de confianza clásica (heurística) aun cuando no haya líneas
                    try:
                        if hasattr(res, "classic_confidence") and res.classic_confidence is not None:
                            db.add(
                                ImportLog(
                                    purchase_id=p.id,
                                    correlation_id=correlation_id,
                                    level="INFO",
                                    stage="heuristic",
                                    event="classic_confidence",
                                    details={
                                        "value": float(res.classic_confidence),
                                        "lines": 0,
                                    },
                                )
                            )
                    except Exception:
                        pass
                except Exception:
                    pass
                await db.commit()
                await db.refresh(p)
                return {
                    "purchase_id": p.id,
                    "status": p.status,
                    "filename": file.filename,
                    "correlation_id": correlation_id,
                    "parsed": {"remito": remito_number, "fecha": remito_dt.isoformat(), "lines": 0, "totals": {"subtotal": 0, "iva": 0, "total": 0}, "hash": f"sha256:{sha256}"},
                    "unmatched_count": 0,
                    "debug": (res.debug if debug_flag else None),
                }
            else:
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
                if debug_flag:
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
        # Normalizaciones adicionales (reparar SKU y bonificación si faltan)
        for ln in lines:
            try:
                title_txt = (ln.get("title") or "").strip()
                qty_num = int(float(ln.get("qty") or 0))
                sku_txt = (ln.get("supplier_sku") or "").strip()
                if sku_txt.isdigit() and qty_num and int(sku_txt) == qty_num:
                    import re as _re
                    cand = _re.findall(r"\b(\d{4,6})\b", title_txt)
                    if cand:
                        ln["supplier_sku"] = cand[-1]
                    else:
                        cand3 = [t for t in _re.findall(r"\b(\d{3,6})\b", title_txt) if int(t) != qty_num]
                        if cand3:
                            ln["supplier_sku"] = cand3[-1]
                if float(ln.get("line_discount") or 0) == 0 and title_txt:
                    import re as _re
                    mdisc = _re.search(r"(-?\d{1,2}(?:[\.,]\d+)?)\s*%", title_txt)
                    if mdisc:
                        try:
                            val = float(str(mdisc.group(1)).replace(".", "").replace(",", "."))
                            ln["line_discount"] = val
                        except Exception:
                            pass
            except Exception:
                pass
        # --- Anti-duplicados: filtrar por SKU y por título normalizado ---
        unique_lines, ignored_by_sku, ignored_by_title = _dedupe_lines(lines)

        # Log de duplicados a ImportLog en WARN
        try:
            if ignored_by_sku:
                db.add(ImportLog(
                    purchase_id=p.id,
                    correlation_id=correlation_id,
                    level="WARN",
                    stage="dedupe",
                    event="ignored_duplicates_by_sku",
                    details={"count": ignored_by_sku},
                ))
            if ignored_by_title:
                db.add(ImportLog(
                    purchase_id=p.id,
                    correlation_id=correlation_id,
                    level="WARN",
                    stage="dedupe",
                    event="ignored_duplicates_by_title",
                    details={"count": ignored_by_title},
                ))
        except Exception:
            pass

        src_lines = unique_lines
        for ln in src_lines:
            sku = (ln.get("supplier_sku") or "").strip()
            title = (ln.get("title") or "").strip() or sku or "(sin título)"
            qty = Decimal(str(ln.get("qty") or 0))
            unit_cost = Decimal(str(ln.get("unit_cost") or 0))
            line_discount = Decimal(str(ln.get("line_discount") or 0))
            supplier_item_id = None
            product_id = None
            if sku:
                sp = await db.scalar(
                    select(SupplierProduct)
                    .where(
                        SupplierProduct.supplier_id==supplier_id,
                        SupplierProduct.supplier_product_id==sku
                    )
                )
                if not sp and title:
                    import re as _re
                    for tok in _re.findall(r"\b(\d{3,6})\b", title):
                        sp = await db.scalar(
                            select(SupplierProduct)
                            .where(
                                SupplierProduct.supplier_id==supplier_id,
                                SupplierProduct.supplier_product_id==tok
                            )
                        )
                        if sp:
                            sku = tok
                            ln["supplier_sku"] = tok
                            break
                if sp:
                    supplier_item_id = sp.id
                    product_id = sp.internal_product_id
            if not supplier_item_id and title and len(title) >= 4:
                try:
                    from rapidfuzz import process, fuzz
                    sp_query = select(SupplierProduct).where(SupplierProduct.supplier_id == supplier_id)
                    all_supplier_products = (await db.execute(sp_query)).scalars().all()
                    choices = {sp.id: (sp.title or "") for sp in all_supplier_products}
                    best_match = process.extractOne(title, choices, scorer=fuzz.WRatio, score_cutoff=85)
                    if best_match:
                        sp_id = best_match[2]
                        sp = await db.get(SupplierProduct, sp_id)
                        if sp:
                            supplier_item_id = sp.id
                            product_id = sp.internal_product_id
                    if not supplier_item_id:
                        from db.models import CanonicalProduct
                        cp_query = select(CanonicalProduct)
                        all_canonicals = (await db.execute(cp_query)).scalars().all()
                        choices_cp = {cp.id: (cp.name or "") for cp in all_canonicals}
                        process.extractOne(title, choices_cp, scorer=fuzz.WRatio, score_cutoff=87)
                except ImportError:
                    key = max((w for w in re.split(r"\W+", title) if len(w) >= 5), key=len, default=title.split(" ")[0])
                    cand_q = select(SupplierProduct).where(
                        SupplierProduct.supplier_id==supplier_id,
                        SupplierProduct.title.ilike(f"%{key}%")
                    ).limit(1)
                    sp = (await db.execute(cand_q)).scalar_one_or_none()
                    if sp:
                        supplier_item_id = sp.id
                        product_id = sp.internal_product_id
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
        try:
            setattr(p, "meta", _sanitize_for_json({
                "correlation_id": correlation_id,
                "filename": file.filename,
                "sha256": sha256,
                "remito_number": remito_number,
                "remito_date": remito_dt.isoformat(),
                "lines_detected": len(lines),
                "lines_unique": len(src_lines),
                "ignored_by_sku": ignored_by_sku,
                "ignored_by_title": ignored_by_title,
            }))
        except Exception:
            pass
        try:
            samples = (res.debug.get("samples") if isinstance(res.debug, dict) else None)
        except Exception:
            samples = None
        db.add(
            AuditLog(
                action="purchase_import",
                table="purchases",
                entity_id=p.id,
                meta=_sanitize_for_json({
                    "correlation_id": correlation_id,
                    "filename": file.filename,
                    "sha256": sha256,
                    "remito_number": remito_number,
                    "remito_date": remito_dt.isoformat(),
                    "lines_detected": len(lines),
                    "lines_unique": len(src_lines),
                    "ignored_by_sku": ignored_by_sku,
                    "ignored_by_title": ignored_by_title,
                    "samples": samples,
                }),
                user_id=None,
                ip=None,
            )
        )
        try:
            for ev in res.events:
                try:
                    details = ev.get("details") or {}
                except Exception:
                    details = {}
                db.add(
                    ImportLog(
                        purchase_id=p.id,
                        correlation_id=correlation_id,
                        level=str(ev.get("level") or "INFO"),
                        stage=str(ev.get("stage") or ""),
                        event=str(ev.get("event") or ""),
                        details=_sanitize_for_json(details),
                    )
                )
            # Registrar métrica de confianza clásica (heurística) para diagnósticos
            try:
                if hasattr(res, "classic_confidence") and res.classic_confidence is not None:
                    db.add(
                        ImportLog(
                            purchase_id=p.id,
                            correlation_id=correlation_id,
                            level="INFO",
                            stage="heuristic",
                            event="classic_confidence",
                            details={
                                "value": float(res.classic_confidence),
                                "lines": len(res.lines or []),
                            },
                        )
                    )
            except Exception:
                pass
        except Exception:
            pass
        await db.commit()
        await db.refresh(p)
        try:
            sub = float(res.totals.get("subtotal") or 0)
        except Exception:
            sub = sum(float(l.get("subtotal") or 0) for l in src_lines) or sum(
                float(l.get("qty") or 0) * float(l.get("unit_cost") or 0) for l in src_lines
            )
        vat = float(p.vat_rate or 0)
        iva = sub * (vat / 100.0)
        total = sub + iva
        response_data = {
            "purchase_id": p.id,
            "status": p.status,
            "filename": file.filename,
            "correlation_id": correlation_id,
            "parsed": {
                "remito": remito_number,
                "fecha": remito_dt.isoformat(),
                "lines": len(src_lines),
                "totals": {"subtotal": round(sub, 2), "iva": round(iva, 2), "total": round(total, 2)},
                "hash": f"sha256:{sha256}",
            },
            "unmatched_count": 0,
            "debug": (res.debug if debug_flag else None),
        }
        return JSONResponse(content=response_data, headers={"X-Correlation-ID": correlation_id})

    except HTTPException as e:
        # Re-raise known API errors, asegurando correlation_id en headers
        cid = locals().get("correlation_id", "unknown")
        e.headers = e.headers or {}
        e.headers["X-Correlation-ID"] = cid
        raise
    except Exception as e:
        # Log full context to backend.log to help diagnose
        cid = locals().get("correlation_id", "unknown")
        try:
            log.exception("Error importando Santaplanta PDF: supplier_id=%s, filename=%s, correlation_id=%s", supplier_id, getattr(file, "filename", "?"), cid)
        except Exception:
            pass
    raise HTTPException(status_code=500, detail="No se pudo importar el remito; revisá backend.log para más detalles", headers={"X-Correlation-ID": cid})


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
    """Devuelve trazas de AuditLog e ImportLog vinculadas a la compra.

    Si `format=json`, retorna la lista cruda; caso contrario `{ items }`.
    """
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


@router.get("/{purchase_id}/logs/files/{filename}")
async def download_purchase_log_file(purchase_id: int, filename: str):
    """Descarga un archivo de logs de una compra (JSON/CSV) de la carpeta data/purchases/{id}/logs.

    Seguridad: restringe el nombre a prefijo 'iaval_changes_' y extensión .json o .csv. Evita path traversal.
    Devuelve Content-Disposition attachment.
    """
    # Validación de nombre
    if not (filename.startswith("iaval_changes_") and (filename.endswith(".json") or filename.endswith(".csv"))):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    root = Path("data") / "purchases" / str(purchase_id) / "logs"
    fpath = root / filename
    try:
        # Resolver y asegurar que está dentro del directorio esperado
        fpath_resolved = fpath.resolve(strict=True)
        if root.resolve() not in fpath_resolved.parents:
            raise HTTPException(status_code=403, detail="Acceso denegado")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except Exception:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    media = "application/json" if filename.endswith(".json") else "text/csv"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return FileResponse(str(fpath), media_type=media, headers=headers)


@router.get("/{purchase_id}/attachments/{attachment_id}/file")
async def download_attachment(purchase_id: int, attachment_id: int, db: AsyncSession = Depends(get_session)):
    """Descarga inline un adjunto de la compra.

    404 si no existe o no corresponde a la compra. Usa Content-Disposition inline.
    """
    att = await db.get(PurchaseAttachment, attachment_id)
    if not att or att.purchase_id != purchase_id:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    pth = Path(att.path)
    if not pth.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    headers = {"Content-Disposition": f"inline; filename=\"{att.filename}\""}
    return FileResponse(str(pth), media_type=att.mime or "application/octet-stream", headers=headers)


@router.post("/import/pop-email", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def import_pop_email(
    supplier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_session),
    kind: str = Query("eml", description="Formato del payload: eml|html|text"),
):
    """Importa una compra desde un email de POP (sin PDF adjunto).

    Soporta dos modos:
    - Subir un archivo .eml (file) → kind=eml
    - Enviar HTML o texto plano (text) → kind=html|text

    Genera SKU sintéticos si POP no envía códigos. Todo queda editable en la UI.
    """
    content: bytes
    upload_filename: str | None = None
    upload_mime: str | None = None

    if kind == "eml":
        ctype = request.headers.get("content-type", "")
        if "multipart/form-data" not in ctype.lower():
            raise HTTPException(status_code=400, detail="Para kind=eml enviá multipart/form-data con campo 'file' (.eml)")
        form = await request.form()
        up = form.get("file")
        if not up:
            raise HTTPException(status_code=400, detail="Adjuntá un archivo .eml en el campo 'file'")
        # Starlette UploadFile o bytes
        if hasattr(up, "read"):
            content = await up.read()  # type: ignore
            upload_filename = getattr(up, "filename", None)  # type: ignore
            upload_mime = getattr(up, "content_type", None)  # type: ignore
        else:
            # Fallback si viene como bytes
            content = bytes(up)
        parsed = parse_pop_email(content, kind="eml")
    elif kind in ("html", "text"):
        payload_text: str | None = None
        if not payload_text:
            # Intentar JSON
            try:
                if request.headers.get("content-type", "").lower().startswith("application/json"):
                    data = await request.json()
                    payload_text = (data or {}).get("text")
            except Exception:
                payload_text = None
        if not payload_text:
            # Intentar form
            try:
                form = await request.form()
                payload_text = form.get("text")  # type: ignore
            except Exception:
                payload_text = None
        if not payload_text:
            raise HTTPException(status_code=400, detail="Falta 'text' con el contenido del email")
        parsed = parse_pop_email(payload_text, kind=kind)
    else:
        raise HTTPException(status_code=400, detail="kind inválido")

    # Unicidad por (supplier_id, remito_number) si logramos extraer remito
    remito_number = parsed.remito_number or (upload_filename if upload_filename else None) or "POP"
    try:
        remito_dt = date.fromisoformat(parsed.remito_date or date.today().isoformat())
    except Exception:
        remito_dt = date.today()

    exists = await db.scalar(select(Purchase).where(Purchase.supplier_id==supplier_id, Purchase.remito_number==remito_number))
    if exists:
        # Idempotente: si ya existe una compra con ese remito para el proveedor, devolverla como éxito
        return {
            "purchase_id": exists.id,
            "status": getattr(exists, "status", None),
            "parsed": {"remito": remito_number, "fecha": (getattr(exists, "remito_date", None) or remito_dt).isoformat() if getattr(exists, "remito_date", None) else remito_dt.isoformat(), "lines": None},
            "duplicate": True,
        }

    # Crear compra
    p = Purchase(supplier_id=supplier_id, remito_number=remito_number, remito_date=remito_dt)
    db.add(p)
    await db.flush()

    # Crear líneas con datos parseados (SKU puede ser sintético; editable luego)
    created = 0
    for ln in parsed.lines:
        title = (ln.title or "").strip() or "(sin título)"
        qty = Decimal(str(ln.qty or 0))
        unit_cost = Decimal(str(ln.unit_cost or 0))
        # Clamps defensivos para evitar overflow / datos absurdos
        try:
            if qty <= 0 or qty >= Decimal('100000'):
                qty = Decimal('1')
        except Exception:
            qty = Decimal('1')
        try:
            if unit_cost < 0 or unit_cost > Decimal('10000000'):
                unit_cost = Decimal('0')
        except Exception:
            unit_cost = Decimal('0')
        db.add(PurchaseLine(
            purchase_id=p.id,
            supplier_item_id=None,
            product_id=None,
            supplier_sku=(ln.supplier_sku or None),
            title=title,
            qty=qty,
            unit_cost=unit_cost,
            line_discount=Decimal("0"),
            state="SIN_VINCULAR",
        ))
        created += 1

    # Guardar eml como adjunto opcional (si vino)
    try:
        if upload_filename:
            root = Path("data") / "purchases" / str(p.id)
            root.mkdir(parents=True, exist_ok=True)
            eml_path = root / (upload_filename or f"pop_{p.id}.eml")
            with open(eml_path, "wb") as fh:
                fh.write(content)
            db.add(PurchaseAttachment(purchase_id=p.id, filename=upload_filename, mime=upload_mime, size=len(content), path=str(eml_path)))
    except Exception:
        pass

    # Audit
    db.add(AuditLog(action="purchase_import_pop_email", table="purchases", entity_id=p.id, meta={
        "lines": created,
        "remito_number": remito_number,
        "remito_date": remito_dt.isoformat(),
        "parse_debug": parsed.debug,
    }))

    await db.commit()
    return {"purchase_id": p.id, "status": p.status, "parsed": {"remito": remito_number, "fecha": remito_dt.isoformat(), "lines": created}}


