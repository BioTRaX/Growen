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


@dataclass
class ImportAttempt:
    """Métrica de intento de extracción, para logging y diagnóstico.

    name: 'plumber' | 'camelot-lattice' | 'camelot-stream' | 'ocr-plumber' | 'ocr-camelot-lattice' | 'ocr-camelot-stream' | 'regex'
    ok: si se obtuvieron líneas (len>0)
    lines_found: cantidad de líneas detectadas
    elapsed_ms: duración
    sample_rows: strings con ejemplos crudos/normalizados
    notes: parámetros usados u observaciones
    """
    name: str
    ok: bool
    lines_found: int
    elapsed_ms: int
    sample_rows: List[str] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)


def _norm_text(s: str) -> str:
    """Normaliza texto: NFKC, reemplaza \xa0, colapsa espacios."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", s)


def _parse_money(s: str) -> Decimal:
    """Convierte un string monetario a Decimal manejando variantes:

    Acepta:
    - "1.234,56" (EU/AR) -> 1234.56
    - "1,234.56" (US) -> 1234.56
    - "1234,56" -> 1234.56
    - "1234.56" -> 1234.56
    - con o sin símbolos de moneda y espacios.
    """
    if not s:
        return Decimal("0")
    s0 = str(s)
    # quitar símbolos y espacios frecuentes
    s1 = re.sub(r"[^0-9.,-]", "", s0).strip()
    if not s1:
        return Decimal("0")
    # Si contiene ambos separadores, decidir por el último como decimal
    has_dot = "." in s1
    has_comma = "," in s1
    try:
        if has_dot and has_comma:
            last_dot = s1.rfind(".")
            last_comma = s1.rfind(",")
            if last_dot > last_comma:
                # Formato estilo US: 1,234.56 -> quitar comas, mantener punto decimal
                canon = s1.replace(",", "")
            else:
                # Formato estilo EU/AR: 1.234,56 -> quitar puntos, cambiar coma a punto
                canon = s1.replace(".", "").replace(",", ".")
        elif has_comma and not has_dot:
            # Probable decimal con coma
            canon = s1.replace(",", ".")
        elif has_dot and not has_comma:
            # Puede ser decimal con punto o miles. Heurística: si hay exactamente 3 dígitos tras el punto y más de 4 antes, tratar como miles.
            parts = s1.split(".")
            if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 2 and len(parts[0]) % 3 == 0:
                canon = s1.replace(".", "")
            else:
                canon = s1
        else:
            canon = s1
        return Decimal(canon)
    except Exception:
        try:
            return Decimal(s1)
        except Exception:
            return Decimal("0")


def _parse_int(s: str) -> int:
    """Extrae el primer entero de un string."""
    if not s:
        return 0
    m = re.search(r"\d+", str(s))
    return int(m.group()) if m else 0


def _extract_expected_counts_and_totals(pdf_text: str) -> Dict[str, Optional[Decimal]]:
    """Extrae "Cantidad De Items: N" e "Importe Total: $ X" del texto del PDF.

    Retorna { expected_items: int|None, importe_total: Decimal|None }.
    """
    t = _norm_text(pdf_text or "")
    expected_items: Optional[int] = None
    importe_total: Optional[Decimal] = None
    try:
        m_items = re.search(r"Cantidad\s+De\s+Items:\s*(\d+)", t, re.I)
        if m_items:
            expected_items = int(m_items.group(1))
    except Exception:
        expected_items = None
    try:
        m_total = re.search(r"Importe\s+Total:\s*\$?\s*([\d\.,]+)", t, re.I)
        if m_total:
            importe_total = _parse_money(m_total.group(1))
    except Exception:
        importe_total = None
    return {"expected_items": expected_items, "importe_total": importe_total}


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
    """Mapea columnas conocidas a sus índices usando fuzzy matching más robusto.

    Compara cada alias individualmente contra cada encabezado y toma el mejor índice con umbral.
    """
    col_map: Dict[str, Optional[int]] = {}
    aliases = {
        "sku": ["codigo", "código", "cod.", "sku", "id"],
        "title": ["producto/servicio", "producto", "servicio", "descripcion", "descripción", "titulo", "descrip"],
        "qty": ["cant.", "cantidad", "cant"],
        "unit_bonif": ["p. unitario bonificado", "p. unit. bonificado", "p unit bonif", "unit bonif", "precio unitario"],
        "pct_bonif": ["% bonif", "bonif %", "% bonif."],
        "subtotal": ["subtotal"],
        "iva": ["iva"],
        "total": ["total"],
    }

    header_norm = [(_norm_text(h or "").lower()) for h in header]
    for key, names in aliases.items():
        best_idx: Optional[int] = None
        best_score = 0
        for i, h in enumerate(header_norm):
            for n in names:
                score = fuzz.WRatio(n.lower(), h)
                if score > best_score:
                    best_score = score
                    best_idx = i
        col_map[key] = best_idx if best_score >= 78 else None
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

        # Detección de fila de continuación (wrap de título):
        # Si no hay SKU y no hay números en columnas clave, pero sí hay título, concatenar al título de la última línea
        def _has_numeric(v: Optional[str]) -> bool:
            if v is None:
                return False
            s = str(v).strip()
            return bool(re.search(r"\d", s))
        numeric_cells = []
        for idx in (i_qty, i_unit, i_pct, i_sub, i_iva, i_tot):
            if idx is not None and idx < len(r):
                numeric_cells.append(r[idx])
        has_any_numeric = any(_has_numeric(v) for v in numeric_cells)
        if raw_title and not sku and not has_any_numeric and lines:
            # concatenar como continuación del título anterior
            try:
                prev = lines[-1]
                j = (" " if (prev.title and not prev.title.endswith(" ")) else "")
                prev.title = (prev.title or "") + j + raw_title
                # agregar muestra
                if len(dbg.setdefault("samples", [])) < 8:
                    dbg["samples"].append({"raw_row": r, "parsed": {"wrap_appended_to": prev.supplier_sku or "", "new_title_excerpt": prev.title[:80]}})
                continue
            except Exception:
                pass

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


def _try_camelot_flavor(pdf_path: Path, flavor: str, params: Dict[str, Any], dbg: Dict[str, Any], events: List[Dict[str, Any]]) -> List[ParsedLine]:
    """Ejecuta Camelot en un flavor específico y devuelve líneas parseadas.

    No levanta, sólo loguea eventos de error.
    """
    out: List[ParsedLine] = []
    raw_tables: List[List[List[str]]] = []
    try:
        import warnings
        try:
            from cryptography.utils import CryptographyDeprecationWarning as _CryDW  # type: ignore
        except Exception:  # pragma: no cover
            _CryDW = DeprecationWarning
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=_CryDW,
                message=r".*ARC4 has been moved to cryptography\.hazmat\.decrepit\.ciphers\.algorithms.*",
            )
            import camelot  # type: ignore
        tables = camelot.read_pdf(str(pdf_path), flavor=flavor, pages="all", **(params or {}))
        events.append({"level": "INFO", "stage": "camelot", "event": "tables_found", "details": {"flavor": flavor, "count": len(tables)}})
        for tbl in tables:
            df_list = tbl.df.astype(str).values.tolist()
            raw_tables.append(df_list)
            out.extend(_extract_lines_from_table(df_list, dbg))
    except Exception as e:
        events.append({"level": "WARN", "stage": "camelot", "event": "flavor_exception", "details": {"flavor": flavor, "msg": str(e)}})
    # Si no pudimos mapear columnas pero sí obtuvimos tablas crudas, aplicar heurística
    if not out and raw_tables:
        try:
            fallback = _heuristic_fallback_rows(raw_tables, events, dbg)
            if fallback:
                out = fallback
        except Exception as _e:
            events.append({"level": "WARN", "stage": "camelot", "event": "heuristic_fallback_error", "details": {"flavor": flavor, "msg": str(_e)}})
    return out


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


def _try_text_multiline_heuristic(text: str, events: List[Dict[str, Any]], expected_items: Optional[int] = None) -> List[ParsedLine]:
    """Heurística textual que une títulos multilínea y detecta qty + precio en la línea de cierre.

    Estrategia:
    - Delimitar la sección de líneas entre la fila de encabezados y el pie ("Cantidad De Items" o "Importe Total").
    - Acumular líneas de título hasta encontrar una línea con patrón de precio monetario y una cantidad entera.
    - Extraer SKU como token numérico 3-6 dígitos distinto de qty y no seguido por unidades (ML, G, KG, L, CM, MM, CC).
    """
    def _find_all_money(line: str) -> list[str]:
        # Captura montos con coma como decimal y puntos opcionales de miles
        return re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", line)
    def _find_qty(tokens: list[str]) -> Optional[int]:
        # tomar el último entero inmediato antes del precio
        for tok in reversed(tokens):
            if re.fullmatch(r"\d+", tok):
                try:
                    return int(tok)
                except Exception:
                    continue
        return None
    U = {"ML", "G", "KG", "L", "CM", "MM", "CC", "GR"}
    def _infer_sku(from_text: str, qty: Optional[int]) -> Optional[str]:
        # buscar 3-6 dígitos no medida y distinto de qty
        for m in re.finditer(r"\b(\d{3,6})\b", from_text):
            val = m.group(1)
            if qty is not None and str(qty) == val:
                continue
            after = from_text[m.end():m.end()+6].strip().upper()
            nxt = re.split(r"\s+", after)[0] if after else ""
            nxt = re.sub(r"[^A-Z0-9]", "", nxt)
            if nxt in U:
                continue
            return val
        return None
    t = text or ""
    # Delimitar región de items
    start_idx = 0
    end_idx = len(t)
    m_header = re.search(r"C[oó]digo.*?Producto/Servicio.*?Cant\.", t, flags=re.I|re.S)
    if m_header:
        start_idx = m_header.end()
    m_footer = re.search(r"Cantidad\s+De\s+Items:|Importe\s+Total:", t, flags=re.I)
    if m_footer:
        end_idx = m_footer.start()
    region = t[start_idx:end_idx]
    lines_raw = [re.sub(r"\s+", " ", ln.strip()) for ln in region.splitlines()]
    buf: list[str] = []
    out: list[ParsedLine] = []
    for raw in lines_raw:
        if not raw:
            continue
        monies = _find_all_money(raw)
        if monies:
            # tokens para qty (antes del precio)
            last_money = monies[-1]
            left = raw.split(last_money)[0].strip()
            tokens = [tok for tok in re.split(r"\s+", left) if tok]
            qty = _find_qty(tokens)
            title = (" ".join(buf + tokens)).strip()
            # limpiar título (quitar repeticiones de espacios)
            title = re.sub(r"\s+", " ", title)
            if not title:
                buf = []
                continue
            sku = _infer_sku(title, qty)
            # Determinar costos: si hay 2+ montos en la línea, asumimos primero=unitario, último=total
            line_total = _parse_money(last_money)
            unit_cost = _parse_money(monies[0]) if len(monies) >= 2 else (line_total / Decimal(qty) if qty else line_total)
            q = Decimal(qty or 0)
            line = ParsedLine(
                supplier_sku=(sku or None),
                title=title,
                qty=q,
                unit_cost_bonif=unit_cost,
                pct_bonif=Decimal("0"),
                subtotal=(line_total if len(monies) >= 1 else (q * unit_cost)),
                iva=None,
                total=(line_total if len(monies) >= 1 else None),
            )
            out.append(line)
            buf = []
            # cortar si alcanzamos esperado
            if expected_items and len(out) >= expected_items:
                break
        else:
            # seguir acumulando como parte del título
            buf.append(raw)
    if out:
        events.append({"level": "INFO", "stage": "fallback", "event": "regex_multiline_ok", "details": {"count": len(out)}})
    else:
        events.append({"level": "INFO", "stage": "fallback", "event": "regex_multiline_empty"})
    return out


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
        # Extraer expectativas del pie (Cantidad de Items / Importe Total)
        exp = _extract_expected_counts_and_totals(text_all)
        expected_items = int(exp.get("expected_items") or 0) or None
        importe_total = exp.get("importe_total")
        try:
            result.events.append({"level": "INFO", "stage": "footer", "event": "expected_from_footer", "details": {"expected_items": expected_items, "importe_total": (float(importe_total) if importe_total is not None else None)}})
        except Exception:
            pass
        header_ok = bool(result.remito_number and result.remito_date)
        attempts: List[ImportAttempt] = []
        # Intento 1: pdfplumber tablas
        from time import perf_counter
        t0 = perf_counter()
        result.lines = _try_pdfplumber_tables(data, result.debug, result.events)
        t1 = perf_counter()
        try:
            attempts.append(ImportAttempt(
                name="plumber",
                ok=bool(result.lines),
                lines_found=len(result.lines or []),
                elapsed_ms=int((t1 - t0) * 1000),
                sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (result.lines or [])[:3]],
                notes={"tables": True},
            ))
        except Exception:
            pass
        if result.lines:
            try:
                result.events.append({"level": "INFO", "stage": "pdfplumber", "event": "lines_detected", "details": {"count": len(result.lines)}})
            except Exception:
                pass
        # Decisión por conteo esperado: si faltan líneas, intentar Camelot por flavor
        if (not result.lines) or (expected_items and len(result.lines) < expected_items):
            flavors = [
                ("lattice", {"line_scale": 40, "strip_text": "\n"}),
                ("stream", {"edge_tol": 200, "row_tol": 10, "column_tol": 10}),
            ]
            best: List[ParsedLine] = list(result.lines or [])
            for fl, kw in flavors:
                t2 = perf_counter()
                cand = _try_camelot_flavor(pdf_path, fl, kw, result.debug, result.events)
                t3 = perf_counter()
                try:
                    attempts.append(ImportAttempt(
                        name=f"camelot-{fl}",
                        ok=bool(cand),
                        lines_found=len(cand or []),
                        elapsed_ms=int((t3 - t2) * 1000),
                        sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (cand or [])[:3]],
                        notes=kw,
                    ))
                except Exception:
                    pass
                if cand and len(cand) > len(best):
                    best = cand
                # Si cerramos el esperado exacto, detener
                if expected_items and cand and len(cand) == expected_items:
                    best = cand
                    break
            if best and (not result.lines or len(best) >= len(result.lines)):
                result.lines = best
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
                # OCR + pdfplumber
                t4 = perf_counter()
                lines_ocr = _try_pdfplumber_tables(data_ocr, result.debug, result.events)
                t5 = perf_counter()
                try:
                    attempts.append(ImportAttempt(
                        name="ocr-plumber",
                        ok=bool(lines_ocr),
                        lines_found=len(lines_ocr or []),
                        elapsed_ms=int((t5 - t4) * 1000),
                        sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (lines_ocr or [])[:3]],
                        notes={"ocr": True},
                    ))
                except Exception:
                    pass
                # Si falta, probar Camelot por flavors
                if (not lines_ocr) or (expected_items and len(lines_ocr) < expected_items):
                    best_ocr = list(lines_ocr or [])
                    for fl, kw in [("lattice", {"line_scale": 40, "strip_text": "\n"}), ("stream", {"edge_tol": 200, "row_tol": 10, "column_tol": 10})]:
                        t6 = perf_counter()
                        cand2 = _try_camelot_flavor(ocr_out, fl, kw, result.debug, result.events)
                        t7 = perf_counter()
                        try:
                            attempts.append(ImportAttempt(
                                name=f"ocr-camelot-{fl}",
                                ok=bool(cand2),
                                lines_found=len(cand2 or []),
                                elapsed_ms=int((t7 - t6) * 1000),
                                sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (cand2 or [])[:3]],
                                notes=kw,
                            ))
                        except Exception:
                            pass
                        if cand2 and len(cand2) > len(best_ocr):
                            best_ocr = cand2
                        if expected_items and cand2 and len(cand2) == expected_items:
                            best_ocr = cand2
                            break
                    if best_ocr and (not lines_ocr or len(best_ocr) >= len(lines_ocr)):
                        lines_ocr = best_ocr
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
                            t8 = perf_counter()
                            lines_ocr2 = _try_pdfplumber_tables(data_ocr2, result.debug, result.events)
                            t9 = perf_counter()
                            try:
                                attempts.append(ImportAttempt(
                                    name="ocr2-plumber",
                                    ok=bool(lines_ocr2),
                                    lines_found=len(lines_ocr2 or []),
                                    elapsed_ms=int((t9 - t8) * 1000),
                                    sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (lines_ocr2 or [])[:3]],
                                    notes={"ocr": True, "retry": 2},
                                ))
                            except Exception:
                                pass
                            if (not lines_ocr2) or (expected_items and len(lines_ocr2) < expected_items):
                                best_ocr2 = list(lines_ocr2 or [])
                                for fl, kw in [("lattice", {"line_scale": 40, "strip_text": "\n"}), ("stream", {"edge_tol": 200, "row_tol": 10, "column_tol": 10})]:
                                    t10 = perf_counter()
                                    cand3 = _try_camelot_flavor(retry_out, fl, kw, result.debug, result.events)
                                    t11 = perf_counter()
                                    try:
                                        attempts.append(ImportAttempt(
                                            name=f"ocr2-camelot-{fl}",
                                            ok=bool(cand3),
                                            lines_found=len(cand3 or []),
                                            elapsed_ms=int((t11 - t10) * 1000),
                                            sample_rows=[str((getattr(x, 'title', '') or '')[:80]) for x in (cand3 or [])[:3]],
                                            notes=kw,
                                        ))
                                    except Exception:
                                        pass
                                    if cand3 and len(cand3) > len(best_ocr2):
                                        best_ocr2 = cand3
                                    if expected_items and cand3 and len(cand3) == expected_items:
                                        best_ocr2 = cand3
                                        break
                                if best_ocr2 and (not lines_ocr2 or len(best_ocr2) >= len(lines_ocr2)):
                                    lines_ocr2 = best_ocr2
                                if lines_ocr2:
                                    result.lines = lines_ocr2
                        except Exception as e:
                            result.events.append({"level": "WARN", "stage": "ocr", "event": "retry_exception", "details": {"error": str(e)}})
            # Limpieza best-effort de archivos temporales OCR
            try:
                for suf in ("_ocr.pdf", "_ocr2.pdf"):
                    p = pdf_path.with_name(pdf_path.stem + suf)
                    if p.exists():
                        p.unlink(missing_ok=True)  # type: ignore[arg-type]
                result.events.append({"level": "INFO", "stage": "cleanup", "event": "ocr_temp_deleted"})
            except Exception:
                pass
        subtotal = sum(line.subtotal for line in result.lines if line.subtotal is not None)
        result.totals = {"subtotal": subtotal, "iva": Decimal("0"), "total": subtotal}
        # Validación contra Importe Total del documento si está disponible
        try:
            if importe_total is not None:
                # Usar suma de 'total' si existe, caso contrario subtotal
                sum_total = sum([(l.total if (l.total is not None and l.total > 0) else (l.subtotal or Decimal("0"))) for l in (result.lines or [])])
                diff = abs((sum_total or Decimal("0")) - importe_total)
                ok_amount = diff <= Decimal("0.11")  # tolerancia de 11 centavos
                result.events.append({"level": ("INFO" if ok_amount else "WARN"), "stage": "validation", "event": "importe_total_check", "details": {"sum_lines": float(sum_total), "importe_total": float(importe_total), "diff": float(diff), "ok": ok_amount}})
        except Exception:
            pass
        # Validación contra expected_items si está disponible
        try:
            if expected_items:
                mismatch = (len(result.lines or []) - int(expected_items))
                ok_count = (mismatch == 0)
                result.events.append({"level": ("INFO" if ok_count else "WARN"), "stage": "validation", "event": "expected_items_check", "details": {"expected": int(expected_items), "got": len(result.lines or []), "ok": ok_count}})
        except Exception:
            pass
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
        # Heurística textual multilínea adicional si difiere el conteo vs expected_items (menos o más)
        try:
            # Sólo si contamos con el texto base
            if 'text_excerpt' in locals():
                # Determinar expected_items si se detectó antes
                exp = _extract_expected_counts_and_totals(locals().get('text_excerpt', '') or '')
                exp_items = int(exp.get('expected_items') or 0) or None
                # Ejecutar si el conteo actual es distinto al esperado (ya sea menor o mayor)
                if (exp_items and (len(result.lines or []) != exp_items)):
                    from time import perf_counter
                    _t0 = perf_counter()
                    extra = _try_text_multiline_heuristic(locals().get('text_excerpt', '') or '', result.events, exp_items)
                    _t1 = perf_counter()
                    try:
                        # Registrar intento
                        attempts = result.debug.setdefault('attempts', []) if isinstance(result.debug, dict) else None
                        if isinstance(attempts, list):
                            attempts.append({
                                'name': 'regex-multiline',
                                'ok': bool(extra),
                                'lines_found': len(extra or []),
                                'elapsed_ms': int((_t1 - _t0) * 1000),
                            })
                    except Exception:
                        pass
                    if extra:
                        # Decidir si reemplazamos: preferir exact match de items; si no, comparar distancia a importe_total
                        def _sum_amount(lines: List[ParsedLine]) -> Decimal:
                            return sum([(ln.total if (ln.total is not None and ln.total > 0) else (ln.subtotal or Decimal("0"))) for ln in (lines or [])])
                        current = result.lines or []
                        choose_extra = False
                        # 1) Si extra logra conteo exacto y el actual no, preferir extra
                        if (exp_items and len(extra) == exp_items and len(current) != exp_items):
                            choose_extra = True
                        # 2) Si ambos difieren, comparar por cercanía de total si tenemos importe_total
                        elif importe_total is not None:
                            diff_curr = abs((_sum_amount(current) or Decimal("0")) - importe_total)
                            diff_extra = abs((_sum_amount(extra) or Decimal("0")) - importe_total)
                            if diff_extra < diff_curr:
                                choose_extra = True
                        # 3) Si no hay total, preferir el que esté más cerca del esperado
                        elif exp_items:
                            if abs(len(extra) - exp_items) < abs(len(current) - exp_items):
                                choose_extra = True
                        if choose_extra:
                            result.events.append({"level": "INFO", "stage": "selection", "event": "replaced_with_regex_multiline", "details": {"prev_count": len(current), "new_count": len(extra)}})
                            result.lines = extra
                            # Update totals
                            subtotal = sum(line.subtotal for line in result.lines if line.subtotal is not None)
                            result.totals = {"subtotal": subtotal, "iva": Decimal("0"), "total": subtotal}
                            # Revalidar conteos
                            try:
                                mismatch = (len(result.lines or []) - int(exp_items))
                                ok_count = (mismatch == 0)
                                result.events.append({"level": ("INFO" if ok_count else "WARN"), "stage": "validation", "event": "expected_items_check", "details": {"expected": int(exp_items), "got": len(result.lines or []), "ok": ok_count}})
                            except Exception:
                                pass
                            # Revalidar importe total si lo teníamos
                            try:
                                if importe_total is not None:
                                    sum_total = sum([(l.total if (l.total is not None and l.total > 0) else (l.subtotal or Decimal("0"))) for l in (result.lines or [])])
                                    diff = abs((sum_total or Decimal("0")) - importe_total)
                                    ok_amount = diff <= Decimal("0.11")
                                    result.events.append({"level": ("INFO" if ok_amount else "WARN"), "stage": "validation", "event": "importe_total_check", "details": {"sum_lines": float(sum_total), "importe_total": float(importe_total), "diff": float(diff), "ok": ok_amount, "after": "regex_multiline"}})
                            except Exception:
                                pass
        except Exception:
            pass
        # Incluir attempts en debug si están
        try:
            if attempts:
                # serializar attempts para debug
                result.debug.setdefault("attempts", [
                    {
                        "name": a.name,
                        "ok": a.ok,
                        "lines_found": a.lines_found,
                        "elapsed_ms": a.elapsed_ms,
                        "sample_rows": a.sample_rows,
                        "notes": a.notes,
                    }
                    for a in attempts
                ])
        except Exception:
            pass
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
