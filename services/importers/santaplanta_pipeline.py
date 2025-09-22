#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: santaplanta_pipeline.py
# NG-HEADER: Ubicación: services/importers/santaplanta_pipeline.py
# NG-HEADER: Descripción: Pipeline robusto para parsear remitos Santa Planta (PDF) con fallback heurístico
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

"""Pipeline robusto para parsear remitos de Santa Planta desde PDF.

Estrategia:
- Extraer header (número de remito y fecha) vía texto (pdfplumber) con normalización.
- Detectar tablas de líneas con pdfplumber y/o Camelot (lattice/stream), con
  heurísticas de fallback cuando no hay estructura clara.
- Si falta texto o header/líneas, invocar OCR (ocrmypdf + Tesseract) y reintentar.
- Emitir eventos y datos de depuración para observabilidad.
"""

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
import os as _os


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
    classic_confidence: float = 0.0
    text_excerpt: Optional[str] = None


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

        # 3) Si aún no encontramos SKU, buscar token de 3-6 dígitos dentro del título,
        # ignorando los que corresponden a unidades de medida (ML, G, KG, L, CM, MM, CC)
        if not sku:
            m3 = re.search(r"\b(\d{3,6})\b", raw_title)
            if m3:
                token = m3.group(1)
                # Verificar si el token está seguido inmediatamente por una unidad (indicador de medida, no SKU)
                after = raw_title[m3.end():m3.end()+6].strip().upper()
                next_token = re.split(r"\s+", after)[0] if after else ""
                next_token = re.sub(r"[^A-Z0-9]", "", next_token)
                units = {"ML", "G", "KG", "L", "CM", "MM", "CC"}
                if next_token in units:
                    # No considerar como SKU; mantener título intacto
                    pass
                else:
                    sku = token
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
        import pdfplumber  # type: ignore
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pi, page in enumerate(pdf.pages):
                events.append({"level": "INFO", "stage": "pdfplumber", "event": "page_info", "details": {"page": pi + 1}})
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                    "join_tolerance": 10,
                }) or []
                try:
                    events.append({"level": "INFO", "stage": "pdfplumber", "event": "tables_found", "details": {"page": pi + 1, "count": len(tables)}})
                except Exception:
                    pass
                for t in tables:
                    all_lines.extend(_extract_lines_from_table(t, dbg))
    except Exception as e:
        events.append({"level": "WARN", "stage": "pdfplumber", "event": "exception", "details": {"msg": str(e)}})
    return all_lines


def _sanitize_tessdata_prefix():
    val = _os.getenv("TESSDATA_PREFIX")
    if not val:
        return
    bad = False
    raw = val
    # Strip quotes
    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
        val = val[1:-1]
        bad = True
    # Remove stray trailing slash+quote artifacts
    val2 = val.replace('"', '').replace("'", '')
    if val2.endswith(('"', "'", '/"', '\\"')):
        val2 = val2.rstrip('/"').rstrip('"')
        bad = True
    # Windows path typically ends without trailing slash
    if val2.endswith(('\\', '/')):
        val2 = val2.rstrip('\\/')
        bad = True
    if bad:
        _os.environ['TESSDATA_PREFIX'] = val2


def _heuristic_fallback_rows(raw_tables: list[list[list[str]]], events: list[dict], dbg: dict) -> list[ParsedLine]:
    raw_lines: list[ParsedLine] = []
    sample_added = 0
    for t in raw_tables:
        if len(t) < 2:
            continue
        for row in t[1:]:  # skip header
            if not any(row):
                continue
            cells = [(_norm_text(c) if c else '') for c in row]
            sku = None
            title = None
            qty = 0
            unit_cost = Decimal('0')
            for c in cells:
                if not sku and re.fullmatch(r"\d{3,6}", c):
                    sku = c
                if title is None:
                    title = c
            for c in cells[1:]:
                if re.fullmatch(r"\d+", c):
                    qty = int(c)
                    break
            for c in reversed(cells):
                if re.search(r"\d[\d\.,]*", c):
                    unit_cost = _parse_money(c)
                    break
            if not title:
                continue
            # Infer SKU from any numeric token 3-6 digits in the title cell only, if still missing
            if not sku and title:
                # Extract numeric tokens (3-6 digits) from title and pick the longest (actual SKU)
                title_tokens = re.findall(r"\b(\d{3,6})\b", title)
                if title_tokens:
                    # Prefer longest token (e.g., '6400' vs '607')
                    sku = max(title_tokens, key=lambda t: (len(t), t))
                    events.append({'level': 'INFO', 'stage': 'fallback', 'event': 'sku_inferred', 'details': {'sku': sku}})
            pl = ParsedLine(supplier_sku=sku, title=title, qty=Decimal(qty), unit_cost_bonif=unit_cost)
            raw_lines.append(pl)
            if sample_added < 5:
                dbg.setdefault('fallback_samples', []).append({'raw_row': row, 'parsed': pl.__dict__})
                sample_added += 1
    if not raw_lines:
        return raw_lines
    events.append({'level': 'INFO', 'stage': 'fallback', 'event': 'heuristic_rows', 'details': {'count': len(raw_lines)}})
    # 1) Si hay líneas con qty>0 o precio>0 asumir que esas son productos y descartar puro metadata
    product_candidates = [l for l in raw_lines if (l.qty and l.qty > 0) or (l.unit_cost_bonif and l.unit_cost_bonif > 0)]
    filtered = product_candidates if product_candidates else list(raw_lines)
    # 2) Si aún muchas líneas y la mayoría tienen qty=0/costo=0, filtrar por patrones de metadata
    if len(filtered) > 1 and len(filtered) >= 5:
        patterns = [
            r"\bS\.?.?R\.?.?L\b", r"\bS\.A\b", r"\bIVA\b", r"\bCUIT\b", r"CONDIC", r"\bVENTA\b",
            r"DIRECCI", r"DOMICILIO", r"\bCLIENTE\b", r"\bDISTRIB", r"\bPROVEED", r"SANTAPLANTA"
        ]
        meta_filtered: list[ParsedLine] = []
        for l in filtered:
            t_upper = l.title.upper()
            if (not l.supplier_sku) and (l.qty == 0) and (l.unit_cost_bonif == 0):
                if any(re.search(p, t_upper) for p in patterns):
                    continue
                # líneas muy cortas (<=3 tokens) sin números -> metadata
                tokens = [tok for tok in re.split(r"\s+", t_upper) if tok]
                if len(tokens) <= 3 and not any(ch.isdigit() for ch in t_upper):
                    continue
            meta_filtered.append(l)
        if meta_filtered and len(meta_filtered) < len(filtered):
            events.append({'level': 'INFO', 'stage': 'fallback', 'event': 'filtered_count', 'details': {'raw': len(raw_lines), 'kept': len(meta_filtered)}})
            filtered = meta_filtered
    # 3) Colapsar si sólo una línea parece item real (qty>0 o precio>0) y el resto parecen metadata
    if len(filtered) > 1:
        real_candidates = [l for l in filtered if (l.qty and l.qty > 0) or (l.unit_cost_bonif and l.unit_cost_bonif > 0)]
        if len(real_candidates) == 1:
            events.append({'level': 'INFO', 'stage': 'fallback', 'event': 'collapsed_single_item', 'details': {'raw': len(filtered)}})
            filtered = real_candidates
    return filtered


def _try_camelot(pdf_path: Path, events: List[Dict[str, Any]], dbg: Dict[str, Any]) -> List[ParsedLine]:
    all_lines: List[ParsedLine] = []
    raw_tables: list[list[list[str]]] = []
    try:
        # Algunos entornos elevan a error un CryptographyDeprecationWarning (ARC4)
        # disparado transitivamente al importar dependencias. Lo silenciamos de forma
        # acotada para permitir el fallback con Camelot sin afectar la política global.
        import warnings
        try:
            from cryptography.utils import CryptographyDeprecationWarning as _CryDW  # type: ignore
        except Exception:  # pragma: no cover
            _CryDW = DeprecationWarning  # fallback genérico si no está disponible
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=_CryDW,
                message=r".*ARC4 has been moved to cryptography\.hazmat\.decrepit\.ciphers\.algorithms.*",
            )
            import camelot  # type: ignore
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
                    raw_tables.append(df_list)
                    all_lines.extend(_extract_lines_from_table(df_list, dbg))
            except Exception as e:
                events.append({"level": "WARN", "stage": "camelot", "event": "flavor_exception", "details": {"flavor": fl, "msg": str(e)}})
    except Exception as e:
        events.append({"level": "WARN", "stage": "camelot", "event": "import_error", "details": {"msg": str(e)}})
    # If no structured lines but we did capture raw tables, emit samples and heuristic fallback
    if not all_lines and raw_tables:
        # log first 3 header rows for diagnostics
        samples = []
        for t in raw_tables[:2]:
            if t:
                samples.append(t[0])
        if samples:
            dbg['camelot_headers_raw'] = samples
        fallback = _heuristic_fallback_rows(raw_tables, events, dbg)
        if fallback:
            all_lines = fallback
    return all_lines


def compute_classic_confidence(lines: List[ParsedLine]) -> float:
    """Heurística refinada de confianza del parser clásico.

    Métricas consideradas (peso entre paréntesis):
    - Proporción de líneas con SKU (0.38)
    - Proporción de líneas con qty > 0 (0.18)
    - Proporción de líneas con unit_cost > 0 (0.12)
    - Diversidad SKU únicos / total (0.12)
    - Densidad numérica (0.20): proporción de caracteres dígitos sobre total en títulos limpios.

    Sanitización de outliers antes del cómputo:
    - Si qty > 10_000 se recorta a 10_000 (protege PDFs con merges extraños).
    - Si unit_cost > 10_000_000 se ignora en la métrica de costo (>10M improbable).

    Escala 0-1. Devuelve 0 si no hay líneas.
    """
    if not lines:
        return 0.0
    # Copia ligera sanitizada
    norm_lines: List[ParsedLine] = []
    for l in lines:
        try:
            qty = l.qty
            if qty and qty > 10000:
                qty = Decimal("10000")
            cost = l.unit_cost_bonif
            if cost and cost > Decimal("10000000"):
                cost = Decimal("0")  # descartar para métrica de costo
            norm = ParsedLine(
                supplier_sku=l.supplier_sku,
                title=l.title,
                qty=qty,
                unit_cost_bonif=cost,
                pct_bonif=l.pct_bonif,
                subtotal=l.subtotal,
                iva=l.iva,
                total=l.total,
            )
            norm_lines.append(norm)
        except Exception:
            norm_lines.append(l)
    lines = norm_lines
    total = len(lines)
    with_sku = sum(1 for l in lines if l.supplier_sku)
    with_qty = sum(1 for l in lines if (l.qty or 0) > 0)
    with_cost = sum(1 for l in lines if (l.unit_cost_bonif or 0) > 0)
    unique_skus = len({l.supplier_sku for l in lines if l.supplier_sku})
    diversity = unique_skus / total if total else 0
    # Densidad numérica en títulos
    digit_chars = 0
    all_chars = 0
    for l in lines:
        t = l.title or ""
        all_chars += len(t)
        digit_chars += sum(1 for ch in t if ch.isdigit())
    density = (digit_chars / all_chars) if all_chars else 0
    score = (
        0.38 * (with_sku / total)
        + 0.18 * (with_qty / total)
        + 0.12 * (with_cost / total)
        + 0.12 * diversity
        + 0.20 * density
    )
    return float(min(1.0, max(0.0, round(score, 4))))


def parse_remito(pdf_path: Path, *, correlation_id: str, use_ocr_auto: bool = True, force_ocr: bool = False, debug: bool = False) -> ParsedResult:
    """Parsea un remito PDF y devuelve líneas normalizadas y metadatos.

    Parámetros:
    - pdf_path: ruta al PDF de entrada.
    - correlation_id: id de correlación para trazas.
    - use_ocr_auto: si no hay texto/líneas, intentará OCR automáticamente.
    - force_ocr: fuerza OCR aunque detecte texto/líneas.
    - debug: incluye muestras y eventos adicionales en `result.debug`.

    Retorna `ParsedResult` con `remito_number`, `remito_date`, `lines`, `totals`,
    `events` y opcionalmente `debug`.
    """
    _sanitize_tessdata_prefix()
    result = ParsedResult(debug={"correlation_id": correlation_id})
    result.events.append({"level": "INFO", "stage": "start", "event": "parse_remito_called", "details": {"pdf": str(pdf_path), "force_ocr": force_ocr, "debug": debug}})
    try:
        data = pdf_path.read_bytes()
        text_excerpt = ""
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(pdf_path)) as pdf:
                pages_text = [(p.extract_text() or "") for p in pdf.pages]
                text_all = "\n".join(pages_text)
                # Guardar excerpt limitado (para prompt IA potencial). Limitar tamaño para no exceder tokens.
                text_excerpt = text_all[:12000]
                try:
                    result.events.append({"level": "INFO", "stage": "header_extract", "event": "text_stats", "details": {"pages": len(pages_text), "len_text": sum(len(t) for t in pages_text)}})
                except Exception:
                    pass
        except Exception as e:
            text_all = ""
            result.events.append({"level": "WARN", "stage": "header_extract", "event": "pdfplumber_failed", "details": {"error": str(e)}})
        result.remito_number, result.remito_date = _parse_header_text(text_all, result.events)
        header_ok = bool(result.remito_number and result.remito_date)
        result.lines = _try_pdfplumber_tables(data, result.debug, result.events)
        if result.lines:
            try:
                result.events.append({"level": "INFO", "stage": "pdfplumber", "event": "lines_detected", "details": {"count": len(result.lines)}})
            except Exception:
                pass
        if not result.lines:
            result.lines = _try_camelot(pdf_path, result.events, result.debug)
        ocr_applied = False
        min_chars_for_text = settings.import_pdf_text_min_chars
        has_enough_text = pdf_has_text(pdf_path, min_chars=min_chars_for_text)
        try:
            result.events.append({"level": "INFO", "stage": "pre_ocr", "event": "pdf_has_text", "details": {"min_chars": min_chars_for_text, "has_enough_text": bool(has_enough_text)}})
        except Exception:
            pass
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
                        import pdfplumber  # type: ignore
                        with pdfplumber.open(io.BytesIO(data_ocr)) as pdf_ocr:
                            text_ocr = "\n".join([(p.extract_text() or "") for p in pdf_ocr.pages])
                            remito_ocr, fecha_ocr = _parse_header_text(text_ocr, result.events)
                            if remito_ocr: result.remito_number = remito_ocr
                            if fecha_ocr: result.remito_date = fecha_ocr
                    except Exception as e:
                        result.events.append({"level": "WARN", "stage": "header_reparse", "event": "pdfplumber_failed_ocr", "details": {"error": str(e)}})
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
        subtotal = sum(line.subtotal for line in result.lines if line.subtotal is not None)
        result.totals = {"subtotal": subtotal, "iva": Decimal("0"), "total": subtotal}
        # Calcular confianza clásica
        try:
            result.classic_confidence = compute_classic_confidence(result.lines)
            result.events.append({"level": "INFO", "stage": "summary", "event": "classic_confidence", "details": {"value": result.classic_confidence}})
        except Exception as _ce:  # pragma: no cover
            result.events.append({"level": "WARN", "stage": "summary", "event": "classic_confidence_error", "details": {"error": str(_ce)}})
        if not result.lines:
            try:
                result.events.append({"level": "WARN", "stage": "summary", "event": "no_lines_after_pipeline", "details": {"ocr_applied": ocr_applied}})
            except Exception:
                pass
        # Fallback final: parser heurístico textual si seguimos sin líneas
        if not result.lines:
            try:
                from services.suppliers.santaplanta_pdf import parse_santaplanta_pdf  # type: ignore
                result.events.append({"level": "INFO", "stage": "fallback", "event": "regex_parser_attempt", "details": {"reason": "no_lines_after_ocr"}})
                # Leer bytes del PDF (si ya hicimos OCR y existe salida, priorizar esa para mejor texto)
                data_for_text: bytes = b""
                try:
                    if 'ocr_applied' in result.debug:
                        ocr_pdf = pdf_path.with_name(pdf_path.stem + "_ocr.pdf")
                        if ocr_pdf.exists():
                            data_for_text = ocr_pdf.read_bytes()
                except Exception:
                    data_for_text = b""
                if not data_for_text:
                    try:
                        data_for_text = pdf_path.read_bytes()
                    except Exception:
                        data_for_text = b""
                if data_for_text:
                    parsed = parse_santaplanta_pdf(data_for_text)
                    hl = parsed.get("lines") or []
                    mapped: list[ParsedLine] = []
                    for ln in hl:
                        try:
                            mapped.append(ParsedLine(
                                supplier_sku=(ln.get("supplier_sku") or None),
                                title=str(ln.get("title") or ""),
                                qty=Decimal(str(ln.get("qty") or "0")),
                                unit_cost_bonif=Decimal(str(ln.get("unit_cost") or "0")),
                                pct_bonif=Decimal(str(ln.get("line_discount") or "0")),
                                subtotal=None,
                                iva=None,
                                total=None,
                            ))
                        except Exception:
                            continue
                    if mapped:
                        result.lines = mapped
                        # Completar header si faltaba
                        if not result.remito_number:
                            rn = parsed.get("remito_number")
                            if rn:
                                result.remito_number = rn
                        if not result.remito_date:
                            rd = parsed.get("remito_date")
                            if rd:
                                result.remito_date = rd
                        result.events.append({"level": "INFO", "stage": "fallback", "event": "regex_parser_ok", "details": {"count": len(mapped)}})
                    else:
                        result.events.append({"level": "WARN", "stage": "fallback", "event": "regex_parser_no_lines"})
                else:
                    result.events.append({"level": "WARN", "stage": "fallback", "event": "regex_parser_skipped", "details": {"reason": "no_data_bytes"}})
            except Exception as _fe:
                result.events.append({"level": "WARN", "stage": "fallback", "event": "regex_parser_error", "details": {"error": str(_fe)}})
        result.events.append({"level": "INFO", "stage": "summary", "event": "done", "details": {"lines": len(result.lines), "ocr": ocr_applied}})
    except Exception as e:  # top-level safeguard
        import traceback
        stack = traceback.format_exc(limit=6)
        result.events.append({"level": "ERROR", "stage": "exception", "event": "unhandled", "details": {"error": str(e), "stack": stack[-900:]}})
    if not debug:
        samples = result.debug.get("samples") if isinstance(result.debug, dict) else None
        # Solo conservar excerpt si debug activo; si no, descartarlo por privacidad
        result.debug = {"samples": samples} if samples else {}
    else:
        # Adjuntar excerpt si se dispone
        try:
            if isinstance(result.debug, dict) and 'excerpt' not in result.debug and 'text_excerpt' not in result.debug:
                # Variable local text_excerpt puede no existir si excepción previa; proteger
                if 'text_excerpt' not in result.debug:
                    result.debug['text_excerpt'] = locals().get('text_excerpt', '')[:4000]
        except Exception:
            pass
    return result
