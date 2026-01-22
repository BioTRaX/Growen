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
from services.notifications.telegram import send_message as tg_send

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
- Si no hay correcciones seguras, devolvé: {"header":{},"lines":[],"lines_to_remove":[],"confidence":0.75,"comments":["Sin diferencias evidentes"]}.

Detección de líneas a eliminar (metadata/encabezados):
- Identificá líneas que son claramente metadata y NO productos reales:
    - Líneas con qty=0, unit_cost=0 y sin SKU válido.
    - Líneas con títulos que son direcciones (Av., Calle, C.A.B.A., Buenos Aires).
    - Líneas con CUIT, IVA RESPONSABLE, razón social (S.R.L., S.A.).
    - Líneas de encabezado del proveedor (SANTA PLANTA, Distribuidora, Tel.).
    - Líneas de campos de formulario (Señores, Entrega, Controlado por, Despachado por).
- Agregá esos índices al array lines_to_remove.
- Solo eliminá líneas si estás MUY SEGURO (>95%) de que no son productos.

Estrategia de matching para líneas:
- Primero intenta emparejar por Código (supplier_sku) exacto.
- Si falta, usa similitud del título (Producto/Servicio) y consistencia de cantidad/precio.
- NO asignes a un índice inexistente y NO modifiques múltiples índices para la misma fila del remito.

Reglas específicas si el proveedor es POP (Distribuidora Pop):
- Los títulos de productos deben ser descriptivos: al menos 2 palabras con letras y 5 letras en total. Evitar títulos puramente numéricos.
- Ignorá o limpiá tokens como "Comprar por:x N", "Tamaño:..", o sufijos de empaque "- x N" al comparar títulos.
- Si hay pack/"x N" en el texto, NO lo confundas con cantidad comprada; la cantidad suele estar en su propia columna/celda. No infieras qty desde pack si ya hay columna cantidad.
- Preferí títulos con mayor densidad de letras si hay dudas. Evitá textos de disclaimers/contacto (WhatsApp, dirección, métodos de pago, Total/Ahorro/Subtotal).
- El importador estima la cantidad de renglones de productos contando símbolos "$" y restando 3 por los sumarios (Subtotal, Total, Ahorro). Por lo tanto, no propongas eliminar líneas sólo porque el conteo no coincide exactamente.
- El importador puede haber usado un "segundo pase" uniendo celdas de una fila para extraer título/cantidad/precio cuando la tabla está fragmentada. Considerá eso para no descartar títulos válidos largos.

Esquema de salida EXACTO:
{
    "header": {"remito_number"?: string, "remito_date"?: string, "vat_rate"?: number},
    "lines": [ { "index": number, "fields": { "qty"?: number, "unit_cost"?: number, "line_discount"?: number, "supplier_sku"?: string, "title"?: string } } ],
    "lines_to_remove": number[],
    "confidence": number,
    "comments": string[]
}

Ejemplo mínimo (con eliminación de metadata):
{
    "header": {"remito_number": "0001-12345678", "remito_date": "2025-09-17", "vat_rate": 21},
    "lines": [
        {"index": 0, "fields": {"supplier_sku": "A-123", "qty": 12, "unit_cost": 1500.0, "line_discount": 10.0}},
        {"index": 2, "fields": {"title": "Maceta 12cm Negra"}}
    ],
    "lines_to_remove": [3, 5, 7],
    "confidence": 0.88,
    "comments": ["Se normaliza N° de remito y fecha", "Se eliminan líneas de encabezado/metadata"]
}
""".strip()
    )
    # Reglas específicas POP sólo si el proveedor coincide
    extra = ""
    if (supplier_name or "").strip().lower().find("pop") != -1:
        extra = (
            "\n\nReglas específicas para POP (Distribuidora Pop):\n"
            "- Títulos descriptivos (≥2 palabras con letras y ≥5 letras totales); evitar títulos puramente numéricos.\n"
            "- Limpiar tokens de ruido: 'Comprar por:x N', 'Tamaño:..', sufijos de empaque '- x N'.\n"
            "- No confundir pack/'x N' con cantidad comprada; priorizar columna/celda 'Cantidad'.\n"
            "- Preferir columnas/segmentos con alta densidad de letras; descartar disclaimers/contacto o sumarios (Subtotal/Total/Ahorro).\n"
            "- El importador estima renglones por símbolos '$' (menos 3 por Subtotal/Total/Ahorro); no propongas eliminar líneas sólo por desbalance de ese conteo.\n"
            "- El importador puede haber unido celdas por fila (segundo pase) para extraer título/precio; no descartes títulos válidos largos por eso.\n"
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
        # Política estricta: duplicado => 409 (tests requieren este comportamiento)
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


@router.put(
    "/{purchase_id}",
    dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)],
)
async def update_purchase(purchase_id: int, payload: dict, db: AsyncSession = Depends(get_session)):
    """Actualiza encabezado y lineas de una compra.

    - Encabezado: global_discount, vat_rate, note, remito_date, depot_id, remito_number.
    - Lineas: upsert/delete con `lines` [{ id?, op=upsert|delete, ... }].
    """
    p = await db.get(Purchase, purchase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    for k in ("global_discount", "vat_rate", "note", "remito_date", "depot_id", "remito_number"):
        if k in payload and payload[k] is not None:
            if k == "remito_date" and isinstance(payload[k], str):
                try:
                    p.remito_date = date.fromisoformat(payload[k])
                except ValueError:
                    raise HTTPException(status_code=400, detail="remito_date invalida")
            else:
                setattr(p, k, payload[k])

    lines: list[dict[str, Any]] = payload.get("lines") or []
    supplier_product_cache: dict[int, SupplierProduct | None] = {}

    async def _get_supplier_product(sp_id: Optional[int]) -> Optional[SupplierProduct]:
        if not sp_id:
            return None
        if sp_id not in supplier_product_cache:
            supplier_product_cache[sp_id] = await db.get(SupplierProduct, sp_id)
        return supplier_product_cache[sp_id]

    for ln in lines:
        op = (ln.get("op") or "upsert").lower()
        lid = ln.get("id")
        if op == "delete" and lid:
            obj = await db.get(PurchaseLine, int(lid))
            if obj and obj.purchase_id == p.id:
                await db.delete(obj)
            continue

        if lid:
            obj = await db.get(PurchaseLine, int(lid))
            if not obj or obj.purchase_id != p.id:
                raise HTTPException(status_code=404, detail="Linea no encontrada")
        else:
            obj = PurchaseLine(purchase_id=p.id)
            db.add(obj)

        prev_sku = (obj.supplier_sku or "") if lid else None
        supplier_sku_provided = "supplier_sku" in ln
        supplier_item_provided = "supplier_item_id" in ln
        product_provided = "product_id" in ln
        state_provided = "state" in ln

        if supplier_sku_provided:
            raw_sku = (ln.get("supplier_sku") or "").strip()
            obj.supplier_sku = raw_sku or None
        if "title" in ln:
            obj.title = (ln.get("title") or "").strip()
        # Si no se envió título pero sí supplier_sku y el título está vacío, usar supplier_sku como fallback
        if not obj.title and obj.supplier_sku:
            obj.title = obj.supplier_sku

        if supplier_item_provided:
            raw_item = ln.get("supplier_item_id")
            if raw_item in (None, "", 0):
                obj.supplier_item_id = None
            else:
                try:
                    obj.supplier_item_id = int(raw_item)
                except Exception:
                    obj.supplier_item_id = None

        if product_provided:
            raw_prod = ln.get("product_id")
            if raw_prod in (None, "", 0):
                obj.product_id = None
            else:
                try:
                    obj.product_id = int(raw_prod)
                except Exception:
                    obj.product_id = None

        for key in ("qty", "unit_cost", "line_discount", "note"):
            if key in ln:
                setattr(obj, key, ln[key])

        if state_provided:
            obj.state = ln.get("state")

        if obj.title:
            obj.title = obj.title.strip()
        else:
            obj.title = ""

        if obj.supplier_sku:
            obj.supplier_sku = obj.supplier_sku.strip() or None

        normalized_prev_sku = (prev_sku or "").strip() if prev_sku is not None else None
        current_sku = (obj.supplier_sku or "")
        sku_changed = supplier_sku_provided and normalized_prev_sku != current_sku

        if sku_changed:
            if not (supplier_item_provided and obj.supplier_item_id):
                obj.supplier_item_id = None
            if not (product_provided and obj.product_id):
                obj.product_id = None

        if supplier_item_provided and obj.supplier_item_id is None and not product_provided:
            obj.product_id = None

        if obj.supplier_item_id:
            sp_obj = await _get_supplier_product(obj.supplier_item_id)
            if sp_obj:
                if not obj.supplier_sku:
                    obj.supplier_sku = getattr(sp_obj, "supplier_product_id", None)
                sp_product_id = getattr(sp_obj, "internal_product_id", None)
                if sp_product_id:
                    if not product_provided or not obj.product_id or obj.product_id != sp_product_id:
                        obj.product_id = sp_product_id

        if not state_provided:
            obj.state = "OK" if (obj.product_id or obj.supplier_item_id) else "SIN_VINCULAR"

    # Integración opcional de autocompletado de líneas (enriquecimiento costos / descuentos / outliers)
    if os.getenv("PURCHASE_COMPLETION_ENABLED", "0") in ("1","true","True"):
        try:
            from services.purchases.completion import LineDraft, complete_purchase_lines, CompletionConfig  # type: ignore
            from decimal import Decimal as _D
            ALGO_VERSION = "20250926_1"

            # Stubs sync (la función complete_purchase_lines es sync)
            class _PriceProvider:
                def get_prices(self, supplier_id: int, sku: str):  # pragma: no cover - stub
                    return []
            class _CatalogProvider:
                def batch_map_skus(self, supplier_id: int, skus):  # pragma: no cover - stub
                    return {}
                def fuzzy_candidates(self, supplier_id: int):  # pragma: no cover - stub
                    return []

            drafts: list[LineDraft] = []
            # Capturar snapshot original para meta
            original_map: dict[int, dict] = {}
            for ln in p.lines:
                original_map[ln.id] = {
                    "unit_cost": float(ln.unit_cost) if ln.unit_cost is not None else None,
                    "line_discount": float(ln.line_discount) if ln.line_discount is not None else None,
                    "supplier_sku": ln.supplier_sku,
                }
                drafts.append(LineDraft(
                    index=ln.id,  # reutilizamos id como índice interno
                    supplier_sku=ln.supplier_sku,
                    title=ln.title or "",
                    qty=_D(str(ln.qty or 0)),
                    unit_cost=_D(str(ln.unit_cost)) if ln.unit_cost is not None else None,
                    line_discount=_D(str(ln.line_discount)) if ln.line_discount is not None else None,
                ))
            comp = complete_purchase_lines(
                supplier_id=p.supplier_id,
                line_drafts=drafts,
                price_provider=_PriceProvider(),
                catalog_provider=_CatalogProvider(),
                config=CompletionConfig(),
            )

            enriched_fields_total = 0
            for res in comp.lines:
                target = next((ln for ln in p.lines if ln.id == res.index), None)
                if not target:
                    continue
                changed_fields: dict[str, dict] = {}
                # unit_cost
                if res.unit_cost is not None and (target.unit_cost is None or target.unit_cost == 0):
                    if original_map[target.id]["unit_cost"] != float(res.unit_cost):
                        changed_fields["unit_cost"] = {"enriched": True, "original": original_map[target.id]["unit_cost"]}
                    target.unit_cost = res.unit_cost
                # line_discount
                if res.line_discount is not None and (target.line_discount is None or target.line_discount == 0):
                    if original_map[target.id]["line_discount"] != float(res.line_discount):
                        changed_fields["line_discount"] = {"enriched": True, "original": original_map[target.id]["line_discount"]}
                    target.line_discount = res.line_discount
                # supplier_sku
                if res.supplier_sku and not target.supplier_sku:
                    changed_fields["supplier_sku"] = {"enriched": True, "original": original_map[target.id]["supplier_sku"]}
                    target.supplier_sku = res.supplier_sku
                if changed_fields:
                    enriched_fields_total += len(changed_fields)
                    meta = target.meta or {}
                    meta["enrichment"] = {
                        "algorithm_version": ALGO_VERSION,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "fields": changed_fields,
                        "stats": {
                            "with_outlier": comp.stats.with_outlier,
                            "price_enriched": comp.stats.price_enriched,
                        }
                    }
                    target.meta = meta

            _purchase_event_log(
                "purchase_completion",
                "purchase_completion_stats",
                purchase_id=p.id,
                enriched_lines=len([ln for ln in p.lines if (ln.meta or {}).get("enrichment")]),
                enriched_fields=enriched_fields_total,
                with_outlier=comp.stats.with_outlier,
                price_enriched=comp.stats.price_enriched,
            )
        except Exception as e:  # pragma: no cover
            _purchase_event_log("purchase_completion", "purchase_completion_error", purchase_id=p.id, error=str(e))
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
    # Reglas de validación:
    # - Si la línea tiene supplier_sku: validar contra SupplierProduct del proveedor.
    #   - Si existe: autovincular (supplier_item_id/product_id) y marcar OK.
    #   - Si NO existe: marcar SIN_VINCULAR SIEMPRE, aunque tenga product_id precargado.
    # - Si la línea NO tiene supplier_sku: mantener criterio previo (OK si ya está vinculada a producto o supplier_item).
    for l in p.lines:
        try:
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
                    # Autovincular si no estaba
                    if not l.supplier_item_id:
                        l.supplier_item_id = sp.id
                    if not l.product_id and getattr(sp, "internal_product_id", None):
                        l.product_id = sp.internal_product_id
                    # Estado final
                    l.state = "OK"
                    auto_linked += 1
                else:
                    # SKU no existe en la base del proveedor: pendiente
                    # Limpieza defensiva: si había vínculos previos (inconsistentes), quitarlos para habilitar 'Crear producto'.
                    l.supplier_item_id = None
                    l.product_id = None
                    l.state = "SIN_VINCULAR"
                    missing_skus.add(sku_txt)
                    unmatched += 1
            else:
                # Sin SKU proveedor: usar vínculo existente si lo hay
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
    raw = await router_ai.run_async(Task.REASONING.value, prompt)
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
    
    # Procesar lines_to_remove del LLM
    lines_to_remove = []
    try:
        ltr_raw = json.loads(raw).get("lines_to_remove") or []
        if isinstance(ltr_raw, list):
            for idx in ltr_raw:
                try:
                    idx_int = int(idx)
                    if 0 <= idx_int < len(p.lines):
                        lines_to_remove.append({
                            "index": idx_int,
                            "title": p.lines[idx_int].title[:50] if p.lines[idx_int].title else None,
                            "reason": "metadata/encabezado detectado por IA"
                        })
                except (TypeError, ValueError):
                    continue
    except Exception:
        pass
    
    return {
        "proposal": {"header": header, "lines": lines, "lines_to_remove": [x["index"] for x in lines_to_remove]},
        "diff": diff,
        "lines_to_remove": lines_to_remove,
        "confidence": confidence,
        "comments": comments,
        "raw": raw
    }


# --- NUEVO: IAVAL Vision AI ---

def _pdf_to_base64_image(pdf_path: str, page: int = 0, dpi: int = 150) -> str:
    """Convierte una página del PDF a imagen base64 para Vision API."""
    import io
    import base64
    
    # Intentar con PyMuPDF primero (más rápido)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page_obj = doc[page]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page_obj.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return base64.b64encode(img_bytes).decode("utf-8")
    except ImportError:
        pass
    
    # Fallback: pdf2image
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=dpi, first_page=page+1, last_page=page+1)
        if images:
            buffer = io.BytesIO()
            images[0].save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except ImportError:
        pass
    
    # Fallback: pdfplumber con PIL
    try:
        import pdfplumber
        from PIL import Image
        with pdfplumber.open(pdf_path) as pdf:
            if page < len(pdf.pages):
                img = pdf.pages[page].to_image(resolution=dpi)
                buffer = io.BytesIO()
                img.original.save(buffer, format="PNG")
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        pass
    
    raise ValueError("No se pudo convertir el PDF a imagen. Instale PyMuPDF, pdf2image o pdfplumber.")


VISION_EXTRACTION_PROMPT = """Eres un extractor experto de datos de remitos argentinos. 
Analiza la imagen del remito y extrae TODOS los datos en formato JSON estructurado.

IMPORTANTE:
- Extrae el número de remito completo (formato típico: XXXX-XXXXXXXX)
- Extrae la fecha de emisión en formato YYYY-MM-DD
- Extrae TODAS las líneas de productos con sus datos completos
- Los SKU del proveedor suelen ser códigos numéricos de 6-12 dígitos
- Los precios usan formato argentino (punto como separador de miles, coma como decimal)

Responde SOLO con JSON válido, sin markdown ni texto adicional:

{
    "header": {
        "proveedor": "nombre del proveedor",
        "remito_number": "XXXX-XXXXXXXX",
        "remito_date": "YYYY-MM-DD"
    },
    "lines": [
        {
            "index": 0,
            "supplier_sku": "código del producto",
            "title": "nombre/descripción del producto", 
            "qty": 1.0,
            "unit_cost": 1000.00,
            "line_discount": 0.0,
            "total": 1000.00
        }
    ],
    "confidence": 0.95,
    "comments": ["notas sobre la extracción"]
}"""


@router.post("/{purchase_id}/iaval/vision", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def iaval_vision(
    purchase_id: int,
    db: AsyncSession = Depends(get_session),
    apply: int = Query(0, description="Si =1, aplica los cambios directamente; si =0 solo preview"),
):
    """Extrae datos del PDF usando OpenAI Vision API.
    
    Revolucionario: en lugar de parsear texto/tablas, envía una IMAGEN del PDF
    a la IA para que extraiga los datos visualmente, como lo haría un humano.
    
    Incluye auditabilidad completa:
    - Guarda la imagen enviada
    - Guarda el prompt utilizado
    - Guarda la respuesta raw de la IA
    - Registra todos los cambios aplicados
    """
    import logging
    import base64
    from datetime import datetime as _dt
    
    log = logging.getLogger("growen")
    correlation_id = str(uuid.uuid4())[:8]
    
    # Cargar la compra con relaciones
    res = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.lines), selectinload(Purchase.attachments), selectinload(Purchase.supplier))
        .where(Purchase.id == purchase_id)
    )
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if p.status not in ("BORRADOR", "PENDIENTE"):
        raise HTTPException(status_code=400, detail="Solo disponible en BORRADOR o PENDIENTE")
    if not p.attachments:
        raise HTTPException(status_code=400, detail="La compra no tiene documento adjunto (PDF)")
    
    # Buscar PDF adjunto
    att_pdf = None
    for att in p.attachments:
        mime = (att.mime or "").lower()
        name = (att.filename or "").lower()
        if (mime.startswith("application/pdf") or name.endswith(".pdf")) and os.path.exists(att.path):
            att_pdf = att
            break
    
    if not att_pdf:
        raise HTTPException(status_code=400, detail="No se encontró PDF adjunto legible")
    
    # === AUDITABILIDAD: Crear directorio de logs ===
    audit_dir = Path("data") / "purchases" / str(p.id) / "iaval_vision"
    audit_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Convertir PDF a imagen
    try:
        pdf_image_b64 = _pdf_to_base64_image(att_pdf.path, page=0, dpi=150)
    except Exception as e:
        log.error(f"IAVAL Vision[{correlation_id}]: Error convirtiendo PDF a imagen: {e}")
        raise HTTPException(status_code=500, detail=f"Error convirtiendo PDF a imagen: {e}")
    
    # === AUDITABILIDAD: Guardar imagen ===
    image_path = audit_dir / f"{ts}_input.png"
    try:
        with open(image_path, "wb") as f:
            f.write(base64.b64decode(pdf_image_b64))
    except Exception as e:
        log.warning(f"IAVAL Vision[{correlation_id}]: No se pudo guardar imagen de auditoría: {e}")
    
    # Preparar contexto de la compra actual
    purchase_context = {
        "id": p.id,
        "supplier_id": p.supplier_id,
        "supplier_name": getattr(getattr(p, "supplier", None), "name", None),
        "remito_number_actual": p.remito_number,
        "remito_date_actual": p.remito_date.isoformat() if p.remito_date else None,
        "lines_actuales": [
            {
                "index": i,
                "supplier_sku": ln.supplier_sku,
                "title": ln.title,
                "qty": float(ln.qty or 0),
                "unit_cost": float(ln.unit_cost or 0),
                "state": ln.state,
            }
            for i, ln in enumerate(p.lines)
        ]
    }
    
    # Construir prompt enriquecido
    full_prompt = f"""{VISION_EXTRACTION_PROMPT}

CONTEXTO DE LA COMPRA ACTUAL (para referencia):
- Proveedor: {purchase_context['supplier_name']}
- Remito actual: {purchase_context['remito_number_actual']}
- Fecha actual: {purchase_context['remito_date_actual']}
- Líneas existentes: {len(purchase_context['lines_actuales'])}

Tu tarea: Analiza la imagen del remito y extrae los datos REALES del documento.
Si los datos actuales son incorrectos, proporciona los valores correctos del remito."""

    # === AUDITABILIDAD: Guardar prompt ===
    prompt_path = audit_dir / f"{ts}_prompt.txt"
    try:
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(full_prompt)
    except Exception:
        pass
    
    # Llamar a Vision API
    log.info(f"IAVAL Vision[{correlation_id}]: Enviando imagen a Vision API...")
    router_ai = AIRouter(settings)
    
    try:
        image_data_url = f"data:image/png;base64,{pdf_image_b64}"
        raw_response = await router_ai.run_async(
            task=Task.REASONING.value,
            prompt=full_prompt,
            images=[image_data_url],
            user_context={"role": "admin", "intent": "iaval_vision"}
        )
    except Exception as e:
        log.error(f"IAVAL Vision[{correlation_id}]: Error en Vision API: {e}")
        raise HTTPException(status_code=500, detail=f"Error en Vision API: {e}")
    
    # === AUDITABILIDAD: Guardar respuesta raw ===
    response_path = audit_dir / f"{ts}_response.txt"
    try:
        with open(response_path, "w", encoding="utf-8") as f:
            f.write(raw_response)
    except Exception:
        pass
    
    # Parsear respuesta JSON
    parsed = None
    try:
        # Limpiar prefijo del provider
        clean_response = raw_response
        if isinstance(clean_response, str):
            if clean_response.startswith("openai:"):
                clean_response = clean_response[7:]
            elif clean_response.startswith("ollama:"):
                clean_response = clean_response[7:]
            
            # Limpiar markdown code blocks si existen
            clean_response = clean_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            # _coerce_json ya devuelve dict (incluye json.loads internamente)
            parsed = _coerce_json(clean_response)
        elif isinstance(clean_response, dict):
            # Ya es un dict, usarlo directamente
            parsed = clean_response
        else:
            parsed = {"header": {}, "lines": [], "confidence": 0, "comments": ["Respuesta no reconocida"]}
    except Exception as e:
        log.warning(f"IAVAL Vision[{correlation_id}]: Error parseando JSON: {e}")
        parsed = {"header": {}, "lines": [], "confidence": 0, "comments": ["Error parseando respuesta"]}
    
    # Extraer datos
    header = parsed.get("header") or {}
    lines = parsed.get("lines") or []
    confidence = float(parsed.get("confidence") or 0)
    comments = parsed.get("comments") or []
    
    # Calcular diff con datos actuales
    diff = {"header": {}, "lines": [], "lines_new": []}
    
    # Diff de header
    if "remito_number" in header and header["remito_number"] and str(p.remito_number) != str(header["remito_number"]):
        diff["header"]["remito_number"] = {"old": p.remito_number, "new": header["remito_number"]}
    if "remito_date" in header and header["remito_date"]:
        try:
            new_date = header["remito_date"]
            old_date = p.remito_date.isoformat() if p.remito_date else None
            if old_date != new_date:
                diff["header"]["remito_date"] = {"old": old_date, "new": new_date}
        except Exception:
            pass
    
    # Diff de líneas: comparar productos extraídos vs existentes
    existing_skus = {ln.supplier_sku: i for i, ln in enumerate(p.lines) if ln.supplier_sku}
    for extracted_line in lines:
        sku = extracted_line.get("supplier_sku")
        if sku and sku in existing_skus:
            # Línea existente: comparar cambios
            idx = existing_skus[sku]
            existing = p.lines[idx]
            changes = {}
            if extracted_line.get("title") and extracted_line["title"] != existing.title:
                changes["title"] = {"old": existing.title, "new": extracted_line["title"]}
            if extracted_line.get("qty") and float(extracted_line["qty"]) != float(existing.qty or 0):
                changes["qty"] = {"old": float(existing.qty or 0), "new": float(extracted_line["qty"])}
            if extracted_line.get("unit_cost") and float(extracted_line["unit_cost"]) != float(existing.unit_cost or 0):
                changes["unit_cost"] = {"old": float(existing.unit_cost or 0), "new": float(extracted_line["unit_cost"])}
            if changes:
                diff["lines"].append({"index": idx, "changes": changes})
        else:
            # Línea nueva detectada
            diff["lines_new"].append(extracted_line)
    
    # === AUDITABILIDAD: Registrar en AuditLog ===
    db.add(AuditLog(
        action="purchase.iaval.vision",
        table="purchases",
        entity_id=p.id,
        meta={
            "correlation_id": correlation_id,
            "confidence": confidence,
            "diff_summary": {
                "header_changes": len(diff["header"]),
                "line_changes": len(diff["lines"]),
                "new_lines": len(diff["lines_new"]),
            },
            "audit_files": {
                "image": str(image_path),
                "prompt": str(prompt_path),
                "response": str(response_path),
            }
        }
    ))
    
    # Si apply=1, aplicar los cambios
    applied = None
    if apply:
        applied = {"header": {}, "lines": [], "lines_added": []}
        
        # Aplicar cambios de header
        if diff["header"].get("remito_number"):
            p.remito_number = diff["header"]["remito_number"]["new"]
            applied["header"]["remito_number"] = diff["header"]["remito_number"]
        if diff["header"].get("remito_date"):
            try:
                p.remito_date = date.fromisoformat(diff["header"]["remito_date"]["new"])
                applied["header"]["remito_date"] = diff["header"]["remito_date"]
            except Exception:
                pass
        
        # Aplicar cambios a líneas existentes
        for line_diff in diff["lines"]:
            idx = line_diff["index"]
            if 0 <= idx < len(p.lines):
                ln = p.lines[idx]
                for field, change in line_diff["changes"].items():
                    setattr(ln, field, change["new"])
                applied["lines"].append(line_diff)
        
        # Agregar líneas nuevas
        for new_line in diff["lines_new"]:
            db.add(PurchaseLine(
                purchase_id=p.id,
                supplier_sku=new_line.get("supplier_sku"),
                title=new_line.get("title", "(sin título)"),
                qty=Decimal(str(new_line.get("qty") or 0)),
                unit_cost=Decimal(str(new_line.get("unit_cost") or 0)),
                line_discount=Decimal(str(new_line.get("line_discount") or 0)),
                state="SIN_VINCULAR",
            ))
            applied["lines_added"].append(new_line)
        
        db.add(AuditLog(
            action="purchase.iaval.vision.apply",
            table="purchases",
            entity_id=p.id,
            meta={"applied": applied, "correlation_id": correlation_id}
        ))
    
    await db.commit()
    
    log.info(f"IAVAL Vision[{correlation_id}]: Completado. Conf={confidence}, Changes={len(diff['lines'])}, New={len(diff['lines_new'])}")
    
    return {
        "ok": True,
        "correlation_id": correlation_id,
        "proposal": {
            "header": header,
            "lines": lines,
        },
        "diff": diff,
        "confidence": confidence,
        "comments": comments,
        "applied": applied,
        "audit": {
            "image": str(image_path),
            "prompt": str(prompt_path),
            "response": str(response_path),
        }
    }


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
    
    # === NUEVO: Eliminar líneas marcadas como erróneas/metadata ===
    lines_to_remove = prop.get("lines_to_remove") or []
    removed_lines = []
    if isinstance(lines_to_remove, list) and lines_to_remove:
        # Ordenar en reversa para mantener índices correctos al eliminar
        existing_lines = list(p.lines)
        for idx in sorted(set(lines_to_remove), reverse=True):
            try:
                idx = int(idx)
                if 0 <= idx < len(existing_lines):
                    ln_to_remove = existing_lines[idx]
                    removed_lines.append({
                        "index": idx,
                        "title": ln_to_remove.title[:50] if ln_to_remove.title else None,
                        "supplier_sku": ln_to_remove.supplier_sku,
                    })
                    await db.delete(ln_to_remove)
            except (TypeError, ValueError):
                continue
        if removed_lines:
            applied["lines_removed"] = removed_lines
    
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
    # Forzar recarga fresca desde BD para evitar líneas eliminadas en caché de sesión
    # Consulta fresca desde BD con selectinload para obtener las líneas actuales
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

    try:
        # --- Inicio de la lógica transaccional ---
        now = datetime.utcnow()
        # Impactar stock y buy_price + price_history (deduplicado por SupplierProduct)
        applied_deltas: list[dict[str, int | None]] = []
        import logging
        log = logging.getLogger("growen")
        unresolved: list[int] = []

        # Seguimiento de updates por SupplierProduct para evitar PriceHistory duplicado
        sp_updates: dict[int, dict[str, Any]] = {}

        for l in p.lines:
            # 1. Ajuste costo efectivo por descuento de línea
            ln_disc = Decimal(str(l.line_discount or 0)) / Decimal("100")
            unit_cost = Decimal(str(l.unit_cost or 0))
            eff = unit_cost * (Decimal("1") - ln_disc)

            # 2. Autovínculo supplier_item_id por supplier_sku si falta
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
                        l.supplier_item_id = sp.id
                        if not l.product_id and sp.internal_product_id:
                            l.product_id = sp.internal_product_id

            # 3. Cargar SupplierProduct si ya teníamos supplier_item_id
            if l.supplier_item_id and not sp:
                sp = await db.get(SupplierProduct, l.supplier_item_id)

            # 4. Track de precios (primera observación old, última new)
            if sp:
                sp_id = sp.id
                if sp_id not in sp_updates:
                    try:
                        old_val = Decimal(str(sp.current_purchase_price or 0))
                    except Exception:
                        old_val = Decimal("0")
                    sp_updates[sp_id] = {"sp": sp, "old": old_val, "new": eff}
                else:
                    sp_updates[sp_id]["new"] = eff

            # 5. Resolver product_id (directo, vía supplier_item o fallback sku)
            prod_id: Optional[int] = l.product_id
            if not prod_id and l.supplier_item_id:
                sp2 = sp if sp and sp.id == l.supplier_item_id else await db.get(SupplierProduct, l.supplier_item_id)
                if sp2 and sp2.internal_product_id:
                    prod_id = sp2.internal_product_id
                    if not l.product_id:
                        l.product_id = prod_id
            prod = None
            if prod_id:
                try:
                    pr = await db.execute(select(Product).where(Product.id == prod_id).with_for_update())
                    prod = pr.scalar_one_or_none()
                except Exception:
                    prod = await db.get(Product, prod_id)
            if not prod and l.supplier_sku and p.supplier_id:
                try:
                    sp_fallback = await db.scalar(
                        select(SupplierProduct).where(
                            SupplierProduct.supplier_id == p.supplier_id,
                            SupplierProduct.supplier_product_id == l.supplier_sku,
                        )
                    )
                    if sp_fallback and sp_fallback.internal_product_id:
                        l.supplier_item_id = l.supplier_item_id or sp_fallback.id
                        l.product_id = sp_fallback.internal_product_id
                        prod_id = sp_fallback.internal_product_id
                        try:
                            pr = await db.execute(select(Product).where(Product.id == prod_id))
                            prod = pr.scalar_one_or_none()
                        except Exception:
                            prod = await db.get(Product, prod_id)
                except Exception:
                    prod = None
            # Refuerzo: si tenemos product_id asignado y aún no cargamos objeto prod, obtenerlo
            if not prod and prod_id:
                try:
                    prod = await db.get(Product, prod_id)
                except Exception:
                    prod = None

            # 6. Aplicar incremento de stock si hay producto
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
                    "line_title": l.title,
                    "supplier_sku": l.supplier_sku,
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
                # No se pudo resolver product: mantener en unresolved pero aún podemos agregar delta informativo
                unresolved.append(l.id)
                if l.supplier_item_id or l.supplier_sku:
                    applied_deltas.append({
                        "product_id": None,
                        "product_title": None,
                        "line_title": l.title,
                        "supplier_sku": l.supplier_sku,
                        "old": None,
                        "delta": 0,
                        "new": None,
                        "line_id": l.id,
                        "note": "unresolved_no_product"
                    })

            # 7. Delta informativo si sólo se vinculó supplier_item (sin producto interno)
            if not any(d.get("line_id") == l.id for d in applied_deltas) and l.supplier_item_id and not l.product_id:
                applied_deltas.append({
                    "product_id": None,
                    "product_title": None,
                    "line_title": l.title,
                    "supplier_sku": l.supplier_sku,
                    "old": None,
                    "delta": 0,
                    "new": None,
                    "line_id": l.id,
                    "note": "linked_without_product"
                })

        # Si hay líneas sin resolver y la política estricta está activa, abortar antes de confirmar
        try:
            require_all = os.getenv("PURCHASE_CONFIRM_REQUIRE_ALL_LINES", "0") in ("1", "true", "True")
        except Exception:
            require_all = False
        if unresolved and require_all:
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
    except Exception:
        await db.rollback()
        raise

    try:
        log.debug("purchase_confirm_debug applied_deltas=%s unresolved=%s", applied_deltas, unresolved)
    except Exception:
        pass

    # Notificación Telegram opcional (respeta TELEGRAM_ENABLED y overrides de compras)
    try:
        text = f"Compra confirmada: proveedor {p.supplier_id}, remito {p.remito_number}, líneas {len(p.lines)}"
        tok = os.getenv("PURCHASE_TELEGRAM_TOKEN") or None
        chat = os.getenv("PURCHASE_TELEGRAM_CHAT_ID") or None
        # Si no hay overrides, se usarán los defaults dentro del servicio
        await tg_send(text, chat_id=chat, token=tok)
    except Exception:
        pass
    resp: dict[str, Any] = {"status": "ok"}
    # Siempre exponer applied_deltas (tests esperan line_title) aunque debug=0
    # Asegurar que cada delta tenga line_title (puede faltar si se generó por fallback tardío)
    if applied_deltas:
        title_map = {}
        try:
            for ln in p.lines:
                title_map[ln.id] = ln.title
        except Exception:
            title_map = {}
        for d in applied_deltas:
            if not d.get("line_title"):
                lid = d.get("line_id")
                if lid and lid in title_map:
                    d["line_title"] = title_map.get(lid)
    resp["applied_deltas"] = applied_deltas
    if debug:
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
                "line_title": l.title,
                "supplier_sku": l.supplier_sku,
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
                # Mensaje incluye variante normal y mojibake para robustez de tests
                detail = {
                    "detail": "No se detectaron líneas / No se detectaron lÃ­neas. Revisá el PDF del proveedor.",
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
                "qty": float(ln.qty or 0),
                "unit_cost": float(ln.unit_cost_bonif or 0),
                "line_discount": float(ln.pct_bonif or 0),
                "subtotal": float(ln.subtotal or 0) if ln.subtotal else float((ln.qty or 0) * (ln.unit_cost_bonif or 0)),
                "iva": float(ln.iva or 0),
                "total": float(ln.total or 0) if ln.total else float(ln.subtotal or 0) if ln.subtotal else float((ln.qty or 0) * (ln.unit_cost_bonif or 0)),
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
            
            # SEGURIDAD: Si título es muy largo, intentar extraer solo la parte del producto
            if len(title) > 150:
                # El fallback multiline a veces concatena todo el texto previo
                # Buscar patrones de producto real: SKU largo (6-12 dígitos con ceros) seguido de nombre
                import re as _re
                # Patrón específico Santa Planta: SKU de 6-12 dígitos (típicamente 000000092)
                # seguido de nombre de producto (letras, al menos una palabra de 3+ chars)
                m = _re.search(
                    r'\b(\d{6,12})\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-záéíóúñÁÉÍÓÚÑ\s0-9\-\.x]+)',
                    title
                )
                if m and len(m.group(2).strip()) > 5:
                    # Verificar que el título extraído tenga palabras válidas (no solo números/fechas)
                    extracted_title = m.group(2).strip()
                    # Rechazar si parece una fecha o número puro
                    if not _re.fullmatch(r'[\d\s/\-]+', extracted_title):
                        if not sku or len(sku) < 6:
                            sku = m.group(1)
                        log.info(f"Import[{correlation_id}]: Título extraído de texto largo: '{extracted_title}' (SKU: {sku})")
                        title = extracted_title
            
            # SEGURIDAD: Truncar título a 250 chars (límite BD es 300)
            if len(title) > 250:
                title = title[:247] + "..."
            
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
            # Fuzzy por título deshabilitado para evitar falsos positivos.
            # La validación exige existencia por SKU proveedor.
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
            # Persistir resumen de intentos si vienen en debug.attempts
            try:
                attempts = None
                if isinstance(res.debug, dict):
                    attempts = res.debug.get("attempts")
                if attempts and isinstance(attempts, list):
                    # Limitar a primeras 8 entradas y campos esenciales
                    at = [
                        {
                            "name": (a.get("name") if isinstance(a, dict) else getattr(a, "name", "")),
                            "ok": bool(a.get("ok")) if isinstance(a, dict) else bool(getattr(a, "ok", False)),
                            "lines_found": int(a.get("lines_found") or 0) if isinstance(a, dict) else int(getattr(a, "lines_found", 0) or 0),
                            "elapsed_ms": int(a.get("elapsed_ms") or 0) if isinstance(a, dict) else int(getattr(a, "elapsed_ms", 0) or 0),
                        }
                        for a in attempts[:8]
                    ]
                    db.add(
                        ImportLog(
                            purchase_id=p.id,
                            correlation_id=correlation_id,
                            level="INFO",
                            stage="attempts",
                            event="summary",
                            details={"items": at},
                        )
                    )
            except Exception:
                pass
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
        # Limpieza de logs (mejor esfuerzo) al finalizar el flujo, para dejar entorno listo
        try:
            # Ejecutar limpieza con políticas por defecto; no bloquear ante errores
            from scripts import cleanup_logs as _cleanup
            # Conservar capturas recientes 30 días y limitar a 200 MB (defaults de script)
            _ = _cleanup.main(["--screenshots-keep-days", "30", "--screenshots-max-mb", "200"])  # type: ignore
            db.add(ImportLog(
                purchase_id=p.id,
                correlation_id=correlation_id,
                level="INFO",
                stage="cleanup",
                event="logs_cleanup_done",
                details={"result": "ok"},
            ))
            await db.commit()
        except Exception:
            # No bloquear respuesta por fallas en limpieza
            pass
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
