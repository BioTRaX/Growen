# NG-HEADER: Nombre de archivo: santaplanta_pipeline.py
# NG-HEADER: Ubicación: services/importers/santaplanta_pipeline.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import io
import re

from services.ocr.utils import pdf_has_text, run_ocrmypdf, ensure_dir


@dataclass
class ParsedLine:
    supplier_sku: Optional[str]
    title: str
    qty: Decimal
    unit_cost_bonif: Decimal
    pct_bonif: Decimal
    subtotal: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    total: Optional[Decimal] = None


@dataclass
class ParsedResult:
    remito_number: Optional[str]
    remito_date: Optional[str]  # ISO date
    lines: List[ParsedLine]
    totals: Dict[str, Decimal]
    debug: Dict[str, Any]
    events: List[Dict[str, Any]]


def _norm_money(s: str) -> Decimal:
    s = (s or "").strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _parse_header_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    remito: Optional[str] = None
    fecha: Optional[str] = None
    m = re.search(r"remito\s*(?:n[º°o]|nro\.?|no\.?|#|num\.?)?\s*[:\-]?\s*([A-Za-z0-9\-/]+)", text, flags=re.I)
    if m:
        remito = m.group(1).strip()
    m = re.search(r"(\d{2})[\-/](\d{2})[\-/](\d{4})", text)
    if m:
        try:
            dt = datetime.strptime(m.group(0), "%d/%m/%Y")
        except ValueError:
            try:
                dt = datetime.strptime(m.group(0), "%d-%m-%Y")
            except ValueError:
                dt = None  # type: ignore
        if dt:
            fecha = dt.date().isoformat()
    return remito, fecha


def _try_pdfplumber_tables(data: bytes, dbg: Dict[str, Any], events: List[Dict[str, Any]]) -> List[ParsedLine]:
    lines: List[ParsedLine] = []
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pi, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                events.append({"level": "INFO", "stage": "pdfplumber", "event": "page_info", "details": {"page": pi + 1, "text_len": len(text)}})
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }) or []
                events.append({"level": "INFO", "stage": "pdfplumber", "event": "tables_found", "details": {"page": pi + 1, "count": len(tables)}})
                for t in tables:
                    if not t or len(t) < 2:
                        continue
                    header = [ (c or "").strip().lower() for c in t[0] ]
                    rows = t[1:]
                    def col_idx(names: List[str]) -> Optional[int]:
                        for i, h in enumerate(header):
                            for n in names:
                                if n in h:
                                    return i
                        return None
                    i_code = col_idx(["código", "codigo", "cód.", "cod"])  # noqa: E501
                    i_title = col_idx(["producto", "servicio"])  # noqa: E501
                    i_qty = col_idx(["cant"])  # noqa: E501
                    i_bonif = col_idx(["% bonif", "%bonif", "bonif"])  # noqa: E501
                    i_unit_bon = col_idx(["unitario bonif", "unitario bonificado", "p. unitario bonificado"])  # noqa: E501
                    i_sub = col_idx(["subtotal"])  # noqa: E501
                    i_iva = col_idx(["iva"])  # noqa: E501
                    i_tot = col_idx(["total", "c/iva"])  # noqa: E501
                    for r in rows:
                        if not isinstance(r, (list, tuple)):
                            continue
                        r = list(r)
                        sku = (r[i_code] if i_code is not None and i_code < len(r) else "") or ""
                        title = (r[i_title] if i_title is not None and i_title < len(r) else "") or ""
                        if not title:
                            continue
                        qty = _norm_money(str(r[i_qty])) if i_qty is not None and i_qty < len(r) else Decimal("0")
                        pct = _norm_money(str(r[i_bonif])) if i_bonif is not None and i_bonif < len(r) else Decimal("0")
                        unit_bon = _norm_money(str(r[i_unit_bon])) if i_unit_bon is not None and i_unit_bon < len(r) else Decimal("0")
                        subtotal = _norm_money(str(r[i_sub])) if i_sub is not None and i_sub < len(r) else None
                        iva = _norm_money(str(r[i_iva])) if i_iva is not None and i_iva < len(r) else None
                        total = _norm_money(str(r[i_tot])) if i_tot is not None and i_tot < len(r) else None
                        ln = ParsedLine(supplier_sku=str(sku).strip() or None, title=str(title).strip(), qty=qty, unit_cost_bonif=unit_bon, pct_bonif=pct, subtotal=subtotal, iva=iva, total=total)
                        lines.append(ln)
                        if len(dbg.setdefault("samples", [])) < 3:
                            dbg["samples"].append({"raw": r, "parsed": ln.__dict__})
    except Exception as e:
        events.append({"level": "WARN", "stage": "pdfplumber", "event": "exception", "details": {"msg": str(e)}})
    return lines


def _try_camelot(pdf_path: Path, events: List[Dict[str, Any]], dbg: Dict[str, Any]) -> List[ParsedLine]:
    lines: List[ParsedLine] = []
    try:
        import camelot  # type: ignore
        flavors = ["lattice", "stream"]
        for fl in flavors:
            try:
                tables = camelot.read_pdf(str(pdf_path), flavor=fl, pages="all")
                events.append({"level": "INFO", "stage": "camelot", "event": "tables_found", "details": {"flavor": fl, "count": len(tables)}})
                for tbl in tables:
                    df = tbl.df
                    if df.shape[0] < 2:
                        continue
                    header = [str(x).strip().lower() for x in list(df.iloc[0])]
                    def col_idx(names: List[str]) -> Optional[int]:
                        for i, h in enumerate(header):
                            for n in names:
                                if n in h:
                                    return i
                        return None
                    i_code = col_idx(["código", "codigo", "cód.", "cod"])  # noqa: E501
                    i_title = col_idx(["producto", "servicio"])  # noqa: E501
                    i_qty = col_idx(["cant"])  # noqa: E501
                    i_bonif = col_idx(["% bonif", "%bonif", "bonif"])  # noqa: E501
                    i_unit_bon = col_idx(["unitario bonif", "unitario bonificado", "p. unitario bonificado"])  # noqa: E501
                    i_sub = col_idx(["subtotal"])  # noqa: E501
                    i_iva = col_idx(["iva"])  # noqa: E501
                    i_tot = col_idx(["total", "c/iva"])  # noqa: E501
                    for _, row in df.iloc[1:].iterrows():
                        title = str(row[i_title]) if i_title is not None else ""
                        if not title or title.strip() == "nan":
                            continue
                        sku = str(row[i_code]) if i_code is not None else ""
                        qty = _norm_money(str(row[i_qty])) if i_qty is not None else Decimal("0")
                        pct = _norm_money(str(row[i_bonif])) if i_bonif is not None else Decimal("0")
                        unit_bon = _norm_money(str(row[i_unit_bon])) if i_unit_bon is not None else Decimal("0")
                        subtotal = _norm_money(str(row[i_sub])) if i_sub is not None else None
                        iva = _norm_money(str(row[i_iva])) if i_iva is not None else None
                        total = _norm_money(str(row[i_tot])) if i_tot is not None else None
                        ln = ParsedLine(supplier_sku=(sku.strip() or None), title=title.strip(), qty=qty, unit_cost_bonif=unit_bon, pct_bonif=pct, subtotal=subtotal, iva=iva, total=total)
                        lines.append(ln)
                        if len(dbg.setdefault("samples", [])) < 3:
                            dbg["samples"].append({"raw": list(row.values), "parsed": ln.__dict__})
            except Exception as e:
                events.append({"level": "WARN", "stage": "camelot", "event": "exception", "details": {"flavor": fl, "msg": str(e)}})
    except Exception as e:
        events.append({"level": "WARN", "stage": "camelot", "event": "import_error", "details": {"msg": str(e)}})
    return lines


def parse_remito(pdf_path: Path, *, correlation_id: str, use_ocr_auto: bool = True, force_ocr: bool = False, debug: bool = False) -> ParsedResult:
    events: List[Dict[str, Any]] = []
    dbg: Dict[str, Any] = {"correlation_id": correlation_id}
    data = pdf_path.read_bytes()

    # Header (texto rápido)
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(pdf_path)) as pdf:
            text_all = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    except Exception:
        text_all = ""
    remito, fecha = _parse_header_text(text_all)
    events.append({"level": "INFO", "stage": "header", "event": "header_parsed", "details": {"remito": remito, "fecha": fecha}})

    # 1) pdfplumber tables
    lines = _try_pdfplumber_tables(data, dbg, events)

    # 2) Camelot si no hay líneas
    if not lines:
        lines = _try_camelot(pdf_path, events, dbg)

    # 3) OCR si corresponde
    ocr_attempted = False
    if (use_ocr_auto and (not pdf_has_text(pdf_path) or not lines)) or force_ocr:
        ocr_attempted = True
        ocr_out = pdf_path.with_name(pdf_path.stem + "_ocr.pdf")
        ok = run_ocrmypdf(pdf_path, ocr_out, force=force_ocr, timeout=int(os.getenv("IMPORT_OCR_TIMEOUT", "120")))
        events.append({"level": "INFO", "stage": "ocr", "event": "ocrmypdf_run", "details": {"ok": ok, "output": str(ocr_out)}})
        if ok and ocr_out.exists():
            data_ocr = ocr_out.read_bytes()
            # reintentos con tablas
            lines = _try_pdfplumber_tables(data_ocr, dbg, events)
            if not lines:
                lines = _try_camelot(ocr_out, events, dbg)

    # Totales simples
    subtotal = sum([(ln.subtotal if ln.subtotal is not None else (ln.qty * ln.unit_cost_bonif)) for ln in lines], Decimal("0"))
    vat_rate = Decimal("0")  # lo aplica la UI/compra
    iva = subtotal * vat_rate / Decimal("100")
    total = subtotal + iva

    events.append({"level": "INFO", "stage": "summary", "event": "done", "details": {"lines": len(lines), "ocr": ocr_attempted}})

    return ParsedResult(
        remito_number=remito,
        remito_date=fecha,
        lines=lines,
        totals={"subtotal": subtotal, "iva": iva, "total": total},
        debug=dbg if debug else {},
        events=events,
    )
