from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import io
import re
import unicodedata
import os
from rapidfuzz import process, fuzz

from agent_core.config import settings
from services.ocr.utils import pdf_has_text, run_ocrmypdf


@dataclass
class ParsedLine:
    supplier_sku: Optional[str] = None
    title: str = ""
    qty: Decimal = Decimal("0")
    unit_cost_bonif: Decimal = Decimal("0")
    pct_bonif: Decimal = Decimal("0")
    subtotal: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    total: Optional[Decimal] = None


@dataclass
class ParsedResult:
    remito_number: Optional[str] = None
    remito_date: Optional[str] = None  # ISO date
    lines: List[ParsedLine] = field(default_factory=list)
    totals: Dict[str, Decimal] = field(default_factory=dict)
    debug: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)


def _norm_text(s: str) -> str:
    """Normaliza texto: NFKC, reemplaza \xa0, colapsa espacios."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", s)


def _parse_money(s: str) -> Decimal:
    """Convierte un string monetario (ej: 1.234,56) a Decimal."""
    if not s:
        return Decimal("0")
    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _parse_int(s: str) -> int:
    """Extrae el primer entero de un string."""
    if not s:
        return 0
    m = re.search(r"\d+", str(s))
    return int(m.group()) if m else 0


def _parse_header_text(text: str, events: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    remito: Optional[str] = None
    fecha: Optional[str] = None
    t = _norm_text(text)
    # Remito: REMITO N°: 0001 - 00099596
    m = re.search(r"REMITO\s*(?:N[º°o]|No|Nro\.?|#|Num\.?)?\s*:\s*(?P<serie>\d{3,4})\s*-\s*(?P<num>\d{5,8})", t, flags=re.I | re.MULTILINE)
    if m:
        remito = f"{m.group('serie')}-{m.group('num')}"
    else:
        m2 = re.search(r"(\d{3,4})\s*-\s*(\d{5,8})", t)
        if m2:
            remito = f"{m2.group(1)}-{m2.group(2)}"
    # Fecha: dd/mm/yyyy o dd-mm-yyyy
    mf = re.search(r"(\d{2})[\-/](\d{2})[\-/](\d{4})", t)
    if mf:
        try:
            dt = datetime.strptime(mf.group(0), "%d/%m/%Y")
        except ValueError:
            try:
                dt = datetime.strptime(mf.group(0), "%d-%m-%Y")
            except ValueError:
                dt = None  # type: ignore
        if dt:
            fecha = dt.date().isoformat()
    events.append({"level": "INFO", "stage": "header", "event": "parsed", "details": {"remito": remito, "fecha": fecha}})
    return remito, fecha


def _map_columns(header: List[str]) -> Dict[str, Optional[int]]:
    """Mapea columnas conocidas a sus índices usando fuzzy matching."""
    col_map = {}
    aliases = {
        "sku": ["codigo", "código", "cod.", "sku", "id"],
        "title": ["producto/servicio", "producto", "servicio", "descripcion", "descripción", "titulo"],
        "qty": ["cant.", "cantidad"],
        "unit_bonif": ["p. unitario bonificado", "p. unit. bonificado", "p unit bonif", "unit bonif"],
        "pct_bonif": ["% bonif", "bonif %"],
        "subtotal": ["subtotal"],
        "iva": ["iva"],
        "total": ["total"],
    }
    
    for key, names in aliases.items():
        best_match = process.extractOne(" ".join(names), header, scorer=fuzz.WRatio, score_cutoff=80)
        col_map[key] = header.index(best_match[0]) if best_match else None
    return col_map


def _extract_lines_from_table(table: List[List[str]], dbg: Dict[str, Any]) -> List[ParsedLine]:
    """Procesa una tabla extraída (lista de listas) y devuelve ParsedLines."""
    lines: List[ParsedLine] = []
    if not table or len(table) < 2:
        return lines

    header = [_norm_text(c or "").lower() for c in table[0]]
    col_map = _map_columns(header)

    i_sku, i_title, i_qty, i_unit, i_pct, i_sub, i_iva, i_tot = (
        col_map.get("sku"), col_map.get("title"), col_map.get("qty"),
        col_map.get("unit_bonif"), col_map.get("pct_bonif"), col_map.get("subtotal"),
        col_map.get("iva"), col_map.get("total")
    )

    for r in table[1:]:
        if not any(r):
            continue

        raw_title = _norm_text(r[i_title]) if i_title is not None and i_title < len(r) else ""
        sku = _norm_text(r[i_sku]) if i_sku is not None and i_sku < len(r) else ""

        # Heurística SKU-en-título
        if not sku:
            # 1) SKU (3-6 dígitos) al inicio, con o sin asterisco
            m = re.match(r"^\s*\*?\s*(?P<sku>\d{3,6})\s+(?P<title>.+)$", raw_title)
            if m:
                sku = m.group("sku")
                raw_title = m.group("title")
            else:
                # 2) Título seguido de SKU al final (fallback)
                m2 = re.match(r"^\s*\*?\s*(?P<title>.*?)[^\d](?P<sku>\d{3,6})\s*$", raw_title)
                if m2:
                    sku = m2.group("sku")
                    raw_title = m2.group("title")

        # 3) Si aún no encontramos SKU, buscar cualquier token de 3-6 dígitos dentro del título
        # (esto cubre casos donde el SKU está en una línea separada dentro de la misma celda)
        if not sku:
            m3 = re.search(r"\b(\d{3,6})\b", raw_title)
            if m3:
                sku = m3.group(1)
                # Eliminar el token numérico del título
                raw_title = (raw_title[:m3.start()] + raw_title[m3.end():]).strip()

        # Limpieza final de título y SKU: quitar asteriscos y colapsar espacios
        title = re.sub(r"\*", "", raw_title).strip()
        title = re.sub(r"\s+", " ", title)
        sku = "".join(re.findall(r"\d+", sku)) if sku else ""

        if not title:
            continue

        qty = _parse_int(r[i_qty]) if i_qty is not None and i_qty < len(r) else 0
        unit_cost = _parse_money(r[i_unit]) if i_unit is not None and i_unit < len(r) else Decimal("0")
        pct_bonif = _parse_money(r[i_pct]) if i_pct is not None and i_pct < len(r) else Decimal("0")

        subtotal = qty * unit_cost
        iva = _parse_money(r[i_iva]) if i_iva is not None and i_iva < len(r) else Decimal("0")
        total = _parse_money(r[i_tot]) if i_tot is not None and i_tot < len(r) else subtotal

        line = ParsedLine(
            supplier_sku=sku or None,
            title=title,
            qty=Decimal(qty),
            unit_cost_bonif=unit_cost,
            pct_bonif=pct_bonif,
            subtotal=subtotal,
            iva=iva,
            total=total
        )
        lines.append(line)

        # Save more samples (helpful for debugging intermittent failures)
        if len(dbg.setdefault("samples", [])) < 8:
            dbg["samples"].append({"raw_row": r, "parsed": line.__dict__})

    return lines


def _try_pdfplumber_tables(data: bytes, dbg: Dict[str, Any], events: List[Dict[str, Any]]) -> List[ParsedLine]:
    all_lines: List[ParsedLine] = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pi, page in enumerate(pdf.pages):
                events.append({"level": "INFO", "stage": "pdfplumber", "event": "page_info", "details": {"page": pi + 1}})
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                    "join_tolerance": 10,
                }) or []
                
                for t in tables:
                    all_lines.extend(_extract_lines_from_table(t, dbg))
    except Exception as e:
        events.append({"level": "WARN", "stage": "pdfplumber", "event": "exception", "details": {"msg": str(e)}})
    return all_lines


def _try_camelot(pdf_path: Path, events: List[Dict[str, Any]], dbg: Dict[str, Any]) -> List[ParsedLine]:
    all_lines: List[ParsedLine] = []
    try:
        import camelot
        flavors = [
            ("lattice", {"line_scale": 40, "strip_text": "\n"}),
            ("stream", {"edge_tol": 200, "row_tol": 10, "column_tol": 10})
        ]
        for fl, kw in flavors:
            try:
                tables = camelot.read_pdf(str(pdf_path), flavor=fl, pages="all", **kw)
                events.append({"level": "INFO", "stage": "camelot", "event": "tables_found", "details": {"flavor": fl, "count": len(tables)}})
                for tbl in tables:
                    df_list = tbl.df.astype(str).values.tolist()
                    all_lines.extend(_extract_lines_from_table(df_list, dbg))
            except Exception as e:
                events.append({"level": "WARN", "stage": "camelot", "event": "flavor_exception", "details": {"flavor": fl, "msg": str(e)}})
    except Exception as e:
        events.append({"level": "WARN", "stage": "camelot", "event": "import_error", "details": {"msg": str(e)}})
    return all_lines


def parse_remito(pdf_path: Path, *, correlation_id: str, use_ocr_auto: bool = True, force_ocr: bool = False, debug: bool = False) -> ParsedResult:
    result = ParsedResult(debug={"correlation_id": correlation_id})
    result.events.append({"level": "INFO", "stage": "start", "event": "parse_remito_called", "details": {"pdf": str(pdf_path), "force_ocr": force_ocr, "debug": debug}})

    data = pdf_path.read_bytes()

    # Header inicial
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            text_all = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    except Exception as e:
        text_all = ""
        result.events.append({"level": "WARN", "stage": "header_extract", "event": "pdfplumber_failed", "details": {"error": str(e)}})

    result.remito_number, result.remito_date = _parse_header_text(text_all, result.events)
    header_ok = bool(result.remito_number and result.remito_date)

    # 1) pdfplumber tables
    result.lines = _try_pdfplumber_tables(data, result.debug, result.events)

    # 2) Camelot si no hay líneas
    if not result.lines:
        result.lines = _try_camelot(pdf_path, result.events, result.debug)

    # 3) OCR si corresponde
    ocr_applied = False
    min_chars_for_text = settings.import_pdf_text_min_chars
    has_enough_text = pdf_has_text(pdf_path, min_chars=min_chars_for_text)
    needs_ocr = not result.lines or not header_ok

    if use_ocr_auto and (needs_ocr or force_ocr or not has_enough_text):
        ocr_start_time = datetime.now()
        ocr_out = pdf_path.with_name(pdf_path.stem + "_ocr.pdf")
        ok, stdout, stderr = run_ocrmypdf(
            pdf_path,
            ocr_out,
            force=(force_ocr or needs_ocr),
            timeout=settings.import_ocr_timeout,
            lang=settings.import_ocr_lang,
        )
        ocr_duration = (datetime.now() - ocr_start_time).total_seconds()
        ocr_applied = True
        result.debug["ocr_applied"] = {"duration_s": ocr_duration}
        result.events.append({"level": "INFO" if ok else "ERROR", "stage": "ocr", "event": "ocrmypdf_run", "details": {"ok": ok, "duration_s": ocr_duration, "output": str(ocr_out), "stdout": (stdout or "")[-300:], "stderr": (stderr or "")[-300:]}})
        
        if ok and ocr_out.exists():
            data_ocr = ocr_out.read_bytes()
            lines_ocr = _try_pdfplumber_tables(data_ocr, result.debug, result.events)
            if not lines_ocr:
                lines_ocr = _try_camelot(ocr_out, result.events, result.debug)
            
            if lines_ocr:
                result.lines = lines_ocr
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(data_ocr)) as pdf_ocr:
                        text_ocr = "\n".join([(p.extract_text() or "") for p in pdf_ocr.pages])
                        remito_ocr, fecha_ocr = _parse_header_text(text_ocr, result.events)
                        if remito_ocr: result.remito_number = remito_ocr
                        if fecha_ocr: result.remito_date = fecha_ocr
                except Exception as e:
                    result.events.append({"level": "WARN", "stage": "header_reparse", "event": "pdfplumber_failed_ocr", "details": {"error": str(e)}})
                # If OCR was applied but produced no lines, attempt one forced retry with different output file
                if not result.lines and not force_ocr:
                    try:
                        retry_out = pdf_path.with_name(pdf_path.stem + "_ocr2.pdf")
                        ok2, stdout2, stderr2 = run_ocrmypdf(
                            pdf_path,
                            retry_out,
                            force=True,
                            timeout=settings.import_ocr_timeout,
                            lang=settings.import_ocr_lang,
                        )
                        dur2 = None
                        if ok2 and retry_out.exists():
                            result.events.append({"level": "INFO" if ok2 else "WARN", "stage": "ocr", "event": "retry_ocr", "details": {"ok": ok2, "output": str(retry_out)}})
                            data_ocr2 = retry_out.read_bytes()
                            lines_ocr2 = _try_pdfplumber_tables(data_ocr2, result.debug, result.events)
                            if not lines_ocr2:
                                lines_ocr2 = _try_camelot(retry_out, result.events, result.debug)
                            if lines_ocr2:
                                result.lines = lines_ocr2
                    except Exception as e:
                        result.events.append({"level": "WARN", "stage": "ocr", "event": "retry_exception", "details": {"error": str(e)}})

    # Totales
    subtotal = sum(line.subtotal for line in result.lines if line.subtotal is not None)
    result.totals = {"subtotal": subtotal, "iva": Decimal("0"), "total": subtotal}

    result.events.append({"level": "INFO", "stage": "summary", "event": "done", "details": {"lines": len(result.lines), "ocr": ocr_applied}})

    # Preserve a minimal set of debug samples even when not running in verbose debug mode.
    if not debug:
        samples = result.debug.get("samples") if isinstance(result.debug, dict) else None
        result.debug = {"samples": samples} if samples else {}

    return result