# NG-HEADER: Nombre de archivo: santaplanta_pdf.py
# NG-HEADER: Ubicación: services/suppliers/santaplanta_pdf.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Parser de remitos Santa Planta (PDF).

Heurístico y tolerante: intenta extraer número de remito, fecha y líneas con
SKU proveedor, título, cantidad, precio unitario y descuento de línea (%).

Se apoya en pdfplumber si está disponible; caso contrario, usa PyPDF2 como
fallback y recurre a expresiones regulares sobre el texto plano.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import io
import logging


log = logging.getLogger("growen")


def _extract_text(data: bytes) -> str:
    log.debug("Iniciando extracción de texto del PDF...")
    try:  # pdfplumber
        import pdfplumber  # type: ignore

        text: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:  # type: ignore[arg-type]
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                text.append(page_text)
                log.debug(f"  - Página {i+1} (pdfplumber): {len(page_text)} caracteres extraídos.")
        full_text = "\n".join(text)
        log.info(f"Extracción con pdfplumber exitosa. Total caracteres: {len(full_text)}")
        return full_text
    except Exception as e:
        log.warning(f"pdfplumber falló: {e}. Intentando con PyPDF2...")
        pass
    try:  # PyPDF2
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        text = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text.append(page_text)
            log.debug(f"  - Página {i+1} (PyPDF2): {len(page_text)} caracteres extraídos.")
        full_text = "\n".join(text)
        log.info(f"Extracción con PyPDF2 exitosa. Total caracteres: {len(full_text)}")
        return full_text
    except Exception as e:
        log.error(f"PyPDF2 también falló: {e}. No se pudo extraer texto del PDF.")
        return ""


def _parse_header(text: str) -> dict:
    remito_number: Optional[str] = None
    remito_date: Optional[str] = None
    log.debug("Parseando encabezado...")

    # Número de remito
    m = re.search(r"remito\s*(?:nro\.?|n°|#|num\.?)?\s*([A-Za-z0-9\-/]+)", text, flags=re.IGNORECASE)
    if m:
        remito_number = m.group(1).strip()
        log.debug(f"  - Número de remito encontrado: '{remito_number}'")
    else:
        log.debug("  - Número de remito no encontrado.")

    # Fecha: dd/mm/yyyy
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
            remito_date = dt.date().isoformat()
            log.debug(f"  - Fecha de remito encontrada: '{remito_date}'")
        else:
            log.debug("  - Fecha de remito encontrada pero no se pudo parsear.")
    else:
        log.debug("  - Fecha de remito no encontrada.")

    return {"remito_number": remito_number, "remito_date": remito_date}


def _norm_num(s: str) -> float:
    s = s.strip()
    # Normaliza miles “.” y decimales “,” a punto
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        try:
            return float(re.sub(r"[^0-9.]+", "", s))
        except Exception:
            return 0.0


def _parse_table_with_pdfplumber(data: bytes) -> Tuple[List[dict], Dict[str, Any]]:
    """Extrae filas con pdfplumber en base a encabezados esperados.
    Devuelve (lines, debug_info).
    """
    log.debug("Intentando parsear tabla con pdfplumber...")
    debug: Dict[str, Any] = {"pages": [], "samples": []}
    out: List[dict] = []
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(io.BytesIO(data)) as pdf:  # type: ignore[arg-type]
            for pi, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                info = {"page": pi + 1, "text_len": len(text)}
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }) or []
                info["tables_found"] = len(tables)
                log.debug(f"  - Página {pi+1}: {len(tables)} tablas encontradas.")
                debug["pages"].append(info)
                for ti, t in enumerate(tables):
                    if not t or len(t) < 2:
                        log.debug(f"    - Tabla {ti+1} descartada (corta o vacía).")
                        continue
                    header = [ (c or "").strip().lower() for c in t[0] ]
                    rows = t[1:]
                    log.debug(f"    - Tabla {ti+1}: {len(rows)} filas, encabezado: {header}")
                    def col_idx(names: List[str]) -> Optional[int]:
                        for i, h in enumerate(header):
                            for n in names:
                                if n in h:
                                    return i
                        return None
                    i_code = col_idx(["código", "codigo", "cod", "cód."])
                    i_title = col_idx(["producto", "servicio"])
                    i_qty = col_idx(["cant"]) 
                    i_bonif = col_idx(["% bonif", "%bonif", "bonif"]) 
                    i_unit_bon = col_idx(["unitario bonif", "unitario bonificado", "p. unitario bonificado"]) 
                    i_sub = col_idx(["subtotal"]) 
                    i_iva = col_idx(["iva"]) 
                    i_tot = col_idx(["total", "c/iva"]) 
                    log.debug(f"      - Mapeo de columnas: code={i_code}, title={i_title}, qty={i_qty}, bonif={i_bonif}, unit_bon={i_unit_bon}, sub={i_sub}, iva={i_iva}, tot={i_tot}")
                    for r_idx, r in enumerate(rows):
                        if not isinstance(r, (list, tuple)):
                            continue
                        r = list(r)
                        sku = (r[i_code] if i_code is not None and i_code < len(r) else "") or ""
                        title = (r[i_title] if i_title is not None and i_title < len(r) else "") or ""
                        qty = _norm_num(str(r[i_qty])) if i_qty is not None and i_qty < len(r) else 0.0
                        disc = _norm_num(str(r[i_bonif])) if i_bonif is not None and i_bonif < len(r) else 0.0
                        unit_bon = _norm_num(str(r[i_unit_bon])) if i_unit_bon is not None and i_unit_bon < len(r) else 0.0
                        subtotal = _norm_num(str(r[i_sub])) if i_sub is not None and i_sub < len(r) else 0.0
                        iva = _norm_num(str(r[i_iva])) if i_iva is not None and i_iva < len(r) else 0.0
                        total = _norm_num(str(r[i_tot])) if i_tot is not None and i_tot < len(r) else 0.0
                        if not title and qty == 0 and unit_bon == 0:
                            log.debug(f"        - Fila {r_idx+1} descartada (vacía): {r}")
                            continue
                        line = {
                            "supplier_sku": (str(sku).strip() or None),
                            "title": str(title).strip(),
                            "qty": qty,
                            "unit_cost": unit_bon,
                            "line_discount": disc,
                            "subtotal": subtotal,
                            "iva": iva,
                            "total": total,
                        }
                        out.append(line)
                        if len(debug["samples"]) < 3:
                            debug["samples"].append({"raw": r, "parsed": line})
                        log.debug(f"        - Fila {r_idx+1} parseada: SKU={line['supplier_sku']}, Título={line['title'][:30]}...")
    except Exception as e:
        log.error(f"Error parseando tabla con pdfplumber: {e}", exc_info=True)
        pass
    log.info(f"Parseo de tabla con pdfplumber finalizado. {len(out)} líneas extraídas.")
    return out, debug


def _parse_lines(text: str) -> list[dict]:
    lines: list[dict] = []
    log.debug("Intentando parseo de líneas con RegEx (fallback)...")
    # Intentar capturar filas tipo: SKU  TÍTULO .... QTY  $PRECIO  DESC%
    # Como heurística, buscamos líneas con un código alfanumérico, texto, cantidad y precio
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        # descartamos encabezados obvios
        if not s or len(s) < 6:
            continue
        if re.search(r"(remito|proveedor|cliente|fecha|subtotal|total)", s, flags=re.I):
            continue
        # Match SKU (alfa-num o con guiones), cantidad y precio
        m = re.search(r"^(?P<sku>[A-Za-z0-9\-_.]{3,})\s+(?P<title>.+?)\s+(?P<qty>\d+[\.,]?\d*)\s+\$?\s*(?P<price>[\d\.,]+)", s)
        if not m:
            continue
        sku = m.group("sku").strip()
        title = m.group("title").strip()
        qty = _norm_num(m.group("qty"))
        unit_cost = _norm_num(m.group("price"))
        # descuento opcional en % en la línea
        disc = 0.0
        mdisc = re.search(r"(%\s*bonif|\bdesc\.?|descuento)\s*:?\s*(\d+[\.,]?\d*)%", s, flags=re.I)
        if mdisc:
            try:
                disc = _norm_num(mdisc.group(2))
            except Exception:
                disc = 0.0
        line = {
            "supplier_sku": sku,
            "title": title,
            "qty": qty,
            "unit_cost": unit_cost,
            "line_discount": disc,
        }
        lines.append(line)
        log.debug(f"  - Línea {i+1} matcheada con RegEx: {line}")
    log.info(f"Parseo con RegEx finalizado. {len(lines)} líneas extraídas.")
    return lines


def parse_santaplanta_pdf(data: bytes) -> dict:
    """Devuelve { remito_number, remito_date, lines }.

    No lanza excepciones; en su lugar, retorna valores faltantes si no se logran
    extraer algunos campos.
    """
    text = _extract_text(data)
    if not text.strip():
        return {"unreadable": True, "remito_number": None, "remito_date": None, "lines": []}
    header = _parse_header(text)
    # Primero intentar con tablas de pdfplumber
    tab_lines, dbg = _parse_table_with_pdfplumber(data)
    lines = tab_lines if tab_lines else _parse_lines(text)
    out = {"remito_number": header.get("remito_number"), "remito_date": header.get("remito_date"), "lines": lines, "unreadable": False}
    # Adjuntar un pequeño debug si hubo tablas
    if dbg:
        out["debug"] = {"text_len": len(text), **dbg}
    return out


__all__ = ["parse_santaplanta_pdf"]
