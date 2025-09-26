# NG-HEADER: Nombre de archivo: pop_email.py
# NG-HEADER: Ubicación: services/importers/pop_email.py
# NG-HEADER: Descripción: Parser de emails de POP (EML/HTML/TEXT) a líneas de compra sin SKU (genera SKU sintético)
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

"""Parser de POP desde email (cuerpo HTML o texto y .eml).

Objetivos:
- Extraer `remito_number` desde el Asunto (p.ej., "Pedido 488344 Completado").
- Estimar `remito_date` desde el header Date o hoy.
- Parsear líneas: título, cantidad, precio unitario (si estuviera) y total/subtotal.
- Si falta `supplier_sku`, generar uno sintético (editable): `POP-YYYYMMDD-###`.

Estrategia parsing:
- EML: preferir parte HTML; fallback a texto plano.
- HTML: buscar tablas con 2+ columnas; detectar encabezados típicos (Producto/Descripción, Cantidad, Precio/Total).
  - Si no hay encabezados claros, interpretar filas como: primera columna = título, alguna otra con número = cantidad y/o precio.
- TEXT: buscar patrones con nombre + qty + precio. Fallback mínimo con título y qty=1.

Nota: Este parser es tolerante; es mejor extraer 80% y editar en la app que bloquear.
"""

from dataclasses import dataclass, field
from datetime import datetime, date as _date
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Dict
import re


@dataclass
class PopLine:
    title: str
    qty: Decimal = Decimal("1")
    unit_cost: Decimal = Decimal("0")
    subtotal: Optional[Decimal] = None
    total: Optional[Decimal] = None
    supplier_sku: Optional[str] = None  # se rellena con sintético si falta


@dataclass
class PopParsed:
    remito_number: Optional[str] = None
    remito_date: Optional[str] = None  # ISO
    lines: List[PopLine] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ").strip())


def _clean_title_pop(title: str) -> str:
    """Limpia ruidos típicos de POP en títulos.
    - Remueve "Comprar por:x N" (con o sin espacios)
    - Remueve sufijos "- x N" cuando es sólo empaque
    - Remueve tokens "Tamaño:NNcm" o similares
    - Normaliza espacios y guiones
    """
    t = title or ""
    # Quitar 'Comprar por:x N' o variantes de espacios
    t = re.sub(r"comprar\s*por\s*:\s*x?\s*\d+", "", t, flags=re.I)
    # Quitar patrones de tamaño explícitos
    t = re.sub(r"tamañ?o\s*:\s*\d+\s*cm", "", t, flags=re.I)
    # Quitar sufijos ' - x N' (empaque) si está al final o pegado
    t = re.sub(r"(?:-|–|—)?\s*x\s*\d+\s*$", "", t, flags=re.I)
    # Normalizar espacios y guiones colgantes
    t = re.sub(r"-\s*$", "", t)
    t = _norm_text(t)
    # Normalizar guiones con espacios
    t = re.sub(r"\s*-\s*", " - ", t)
    t = _norm_text(t)
    return t


def _title_is_valid_pop(title: str) -> bool:
    """Regla POP: al menos 2 palabras con letras y >=5 letras en total."""
    t = title or ""
    tokens = [w for w in re.split(r"\s+", t) if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", w)]
    if len(tokens) < 2:
        return False
    letters_total = len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", t))
    return letters_total >= 5


def _parse_money(s: str) -> Decimal:
    """Parser POP para montos del email.

    Regla observada: las comas se usan como separador de miles (no decimales) en el subtotal.
    En este contexto, los unitarios no vienen expresados, por lo que el valor monetario que
    aparece junto a la línea corresponde al subtotal del producto.

    Estrategia: eliminar todo excepto dígitos y parsear como entero decimal.
    Ejemplos: "$ 4,113" -> 4113; "$ 2,335" -> 2335.
    """
    try:
        digits = re.sub(r"[^0-9]", "", (s or ""))
        return Decimal(digits or "0")
    except Exception:
        return Decimal("0")


def _extract_from_subject(subj: str) -> Tuple[Optional[str], Optional[str]]:
    # Remito/pedido: preferimos números significativos
    rem = None
    if subj:
        m = re.search(r"\b(?:Pedido|Remito|Orden)\s*(\d{4,})\b", subj, flags=re.I)
        if m:
            rem = m.group(1)
    return rem, None


def _extract_from_text_body(text: str) -> Optional[str]:
    """Intenta extraer número de Pedido/Remito desde texto libre."""
    if not text:
        return None
    m = re.search(r"\b(?:Pedido|Remito|Orden)\s*(\d{4,})\b", text, flags=re.I)
    return m.group(1) if m else None


def _parse_eml(data: bytes) -> Tuple[str, Optional[str], str, str]:
    """Devuelve (subject, date_iso?, best_body_html, best_body_text)."""
    import email
    from email import policy
    msg = email.message_from_bytes(data, policy=policy.default)
    subj = str(msg.get('Subject') or '')
    dt_iso: Optional[str] = None
    try:
        from email.utils import parsedate_to_datetime
        dd = parsedate_to_datetime(msg.get('Date')) if msg.get('Date') else None
        if dd:
            dt_iso = dd.date().isoformat()
    except Exception:
        pass
    body_html = ""
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            if ctype == 'text/html' and not body_html:
                body_html = part.get_content()
            elif ctype == 'text/plain' and not body_text:
                body_text = part.get_content()
    else:
        ctype = (msg.get_content_type() or '').lower()
        if ctype == 'text/html':
            body_html = msg.get_content()
        else:
            body_text = msg.get_content()
    return subj, dt_iso, body_html, body_text


def _parse_html(body_html: str, dbg: Dict[str, Any]) -> List[PopLine]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body_html, 'html.parser')
    tables = soup.find_all('table')
    lines: List[PopLine] = []
    dbg.setdefault('html_tables', len(tables))
    best_rows: List[List[str]] = []
    table_candidates_dbg: List[Dict[str, Any]] = []
    
    def _is_noise_title(title: str) -> bool:
        """Heurística simple para descartar filas que no son productos."""
        t = title.lower()
        noise_tokens = [
            'whatsapp', 'atención al cliente', 'atencion al cliente',
            'distribuidora pop', 'todos derechos reservados', '©', '(c)',
            'dirección de facturación', 'direccion de facturacion', 'tel:', 'email',
            'esta es una orden de pedido', 'precios pueden sufrir modificaciones',
        ]
        return any(tok in t for tok in noise_tokens)
    # Elegimos la tabla priorizando: encabezados comerciales + filas con moneda ($) + cantidad de filas
    best_score: int = -1
    best_meta: Dict[str, Any] = {}
    # Elegimos la tabla con más filas y columnas >= 2
    for t in tables:
        rows = []
        for tr in t.find_all('tr'):
            cols = [_norm_text(td.get_text(' ')) for td in (tr.find_all('td') or tr.find_all('th'))]
            if cols and any(c for c in cols):
                rows.append(cols)
        # preferimos la tabla con más filas, y como desempate, la que tenga encabezados más "comerciales"
        if rows and len(rows[0]) >= 2:
            def header_score(rr0: List[str]) -> int:
                h = [c.lower() for c in rr0]
                score = 0
                for want in ('producto', 'descrip', 'titulo', 'detalle', 'articulo', 'artículo'):
                    score += sum(1 for c in h if want in c)
                for want in ('cant', 'cantidad', 'unidades'):
                    score += sum(1 for c in h if want in c)
                for want in ('precio', 'unitario', 'p. unit', 'subtotal', 'total'):
                    score += sum(1 for c in h if want in c)
                return score
            hdr = header_score(rows[0])
            money_rows = 0
            for r in rows[1:]:
                try:
                    if any(('$' in c) or re.search(r"\$\s*[0-9\.,]+", c) for c in r):
                        money_rows += 1
                except Exception:
                    pass
            # Ponderación: headers (x3) + filas con dinero (x2) + cantidad de filas (x1)
            score = hdr * 3 + money_rows * 2 + len(rows)
            table_candidates_dbg.append({'rows': len(rows), 'cols': max((len(r) for r in rows), default=0), 'header_score': hdr, 'money_rows': money_rows, 'score': score})
            if score > best_score or (score == best_score and len(rows) > len(best_rows)):
                best_score = score
                best_rows = rows
                best_meta = table_candidates_dbg[-1]
    if table_candidates_dbg:
        dbg['table_candidates'] = table_candidates_dbg
    if best_meta:
        dbg['table_selected'] = best_meta
    if not best_rows:
        # Como fallback, buscar listados por <li>
        for li in soup.find_all('li'):
            txt = _norm_text(li.get_text(' '))
            if len(txt) >= 4:
                lines.append(_parse_line_from_text(txt))
        return [ln for ln in lines if ln.title]
    header = [c.lower() for c in best_rows[0]]
    # Detectar índices
    def idx(names: List[str]) -> Optional[int]:
        for i, h in enumerate(header):
            for n in names:
                if n in h:
                    return i
        return None
    i_title = idx(['producto', 'descrip', 'titulo', 'detalle', 'articulo', 'artículo']) or 0
    i_qty = idx(['cant', 'cantidad', 'unidades'])
    i_unit = idx(['precio', 'unitario', 'p. unit'])
    i_sub = idx(['subtotal'])
    dbg.setdefault('columns_selected', {'title': i_title, 'qty': i_qty, 'unit': i_unit, 'subtotal': i_sub, 'method': 'header'})
    # Si el header elegido para título produce muchos títulos inválidos, intentar elegir la columna con más letras promedio
    def _letters_density(col_index: int) -> float:
        vals = [best_rows[r][col_index] for r in range(1, len(best_rows)) if col_index < len(best_rows[r])]
        if not vals:
            return 0.0
        letters = sum(len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", v)) for v in vals)
        return letters / max(1, len(vals))
    sample_count = min(10, max(0, len(best_rows) - 1))
    if sample_count > 0:
        invalid = 0
        for r in range(1, 1 + sample_count):
            rr = best_rows[r]
            cand = _clean_title_pop(_norm_text(rr[i_title])) if i_title is not None and i_title < len(rr) else ''
            if not _title_is_valid_pop(cand):
                invalid += 1
        if invalid >= max(3, sample_count // 2):
            cols = len(max(best_rows, key=len))
            densities = [(ci, _letters_density(ci)) for ci in range(cols)]
            densities.sort(key=lambda x: x[1], reverse=True)
            if densities and densities[0][1] > 0:
                i_title = densities[0][0]
                dbg['retuned_title_col'] = i_title
                dbg['columns_selected'] = {'title': i_title, 'qty': i_qty, 'unit': i_unit, 'subtotal': i_sub, 'method': 'density'}
    # Conteo de filas con símbolo $ en la tabla seleccionada (para diagnóstico y heurística)
    money_rows_best = 0
    for rr in best_rows[1:]:
        try:
            if any(('$' in c) or re.search(r"\$\s*[0-9\.,]+", c) for c in rr):
                money_rows_best += 1
        except Exception:
            pass
    dbg['table_money_rows_selected'] = money_rows_best

    unit_from_subtotal_count = 0
    for rr in best_rows[1:]:
        if not any(rr):
            continue
        raw_title = _norm_text(rr[i_title]) if i_title is not None and i_title < len(rr) else ''
        title = _clean_title_pop(raw_title)
        if not title:
            continue
        # Descartar títulos sin letras o demasiado pobres
        if not _title_is_valid_pop(title):
            continue
        if _is_noise_title(title):
            # descartar filas de disclaimers o contacto
            continue
        qty = Decimal("1")
        if i_qty is not None and i_qty < len(rr):
            # tomar solo el primer número plausible de la celda, no concatenar todos los dígitos
            mqty = re.search(r"(\d{1,6})(?:[.,](\d{1,2}))?", rr[i_qty])
            if mqty:
                try:
                    if mqty.group(2):
                        qty = Decimal(f"{mqty.group(1)}.{mqty.group(2)}")
                    else:
                        qty = Decimal(mqty.group(1))
                except Exception:
                    pass
        else:
            # Intentar extraer empaque del título sólo si no hay columna cantidad (no confundir pack con cantidad comprada)
            mqty2 = re.search(r"comprar\s*por\s*:\s*x?\s*(\d{1,4})", raw_title, flags=re.I) or re.search(r"(?:^|\s|-)x\s*(\d{1,4})\b", raw_title, flags=re.I)
            if mqty2:
                # No modificamos qty (que es cantidad de packs), sólo dejamos constancia en debug
                dbg.setdefault('pack_hint', 0)
                dbg['pack_hint'] += 1
        # POP: no viene el precio unitario; el monto que aparece es el subtotal de la línea.
        # Intentar detectar el subtotal desde la columna 'Subtotal'; si no existe, buscar el primer monto de la fila.
        subtotal: Optional[Decimal] = None
        if i_sub is not None and i_sub < len(rr):
            subtotal = _parse_money(rr[i_sub])
        if subtotal is None or subtotal == 0:
            # Buscar en todas las celdas un valor monetario plausible
            for cc in rr:
                if "$" in cc or re.search(r"\$\s*[0-9\.,]+", cc):
                    val = _parse_money(cc)
                    if val > 0:
                        subtotal = val
                        break
        # Calcular precio unitario desde subtotal/cantidad si es posible
        unit_cost = Decimal("0")
        if subtotal and qty > 0:
            try:
                unit_cost = (subtotal / qty).quantize(Decimal("0.01"))
                unit_from_subtotal_count += 1
            except Exception:
                unit_cost = Decimal("0")
        # clamps de seguridad
        if qty <= 0 or qty >= Decimal('100000'):
            qty = Decimal('1')
        if unit_cost < 0 or unit_cost > Decimal('10000000'):
            unit_cost = Decimal('0')
        lines.append(PopLine(title=title, qty=qty, unit_cost=unit_cost, subtotal=subtotal))
    lines = [ln for ln in lines if ln.title]
    if unit_from_subtotal_count:
        dbg['unit_from_subtotal_html'] = unit_from_subtotal_count

    # Si la tabla está muy fragmentada (muchas columnas) o subcontamos respecto a filas con $, hacer un segundo pase:
    # unir celdas por fila y parsear con lógica de texto por presencia de $.
    try:
        many_cols = len(header) >= 20 or max((len(r) for r in best_rows), default=0) >= 20
    except Exception:
        many_cols = False
    target_min = max(0, money_rows_best - 3)
    if many_cols or (target_min and len(lines) < target_min):
        def _extract_candidate_title_from_row(txt_row: str) -> str:
            # Elegir mejor segmento con letras que no sea ruido típico y con 2+ palabras
            candidates = re.split(r"\s+-\s+|·|\|", txt_row)
            noise_terms = [
                'pedido completado', 'el pedido se encuentra', 'detalles', 'método de pago', 'metodo de pago',
                'subtotal', 'total', 'ahorro', 'envío', 'envio', 'retiro por pop', 'pago en efectivo',
                'dirección de facturación', 'direccion de facturacion', 'email:', 'tel:'
            ]
            scored: list[tuple[int, str]] = []
            for seg in candidates:
                s = _clean_title_pop(seg)
                if not _title_is_valid_pop(s):
                    continue
                low = s.lower()
                if any(term in low for term in noise_terms):
                    continue
                letters = len(re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", s))
                scored.append((letters, s))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                # limitar tamaño para no traer párrafos enteros
                return scored[0][1][:120]
            return ''
        joined_extra: List[PopLine] = []
        seen_titles = {ln.title for ln in lines}
        for rr in best_rows[1:]:
            txt_row = _norm_text(" ".join([c for c in rr if c]))
            if "$" in txt_row and re.search(r"\$\s*[0-9\.,]+", txt_row) and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", txt_row):
                ln = _parse_line_from_text(txt_row)
                # Mejorar título tomando un candidato contextual de la fila
                cand = _extract_candidate_title_from_row(txt_row)
                if cand:
                    ln.title = cand
                if ln.title and ln.title not in seen_titles and _title_is_valid_pop(ln.title):
                    joined_extra.append(ln)
                    seen_titles.add(ln.title)
        if joined_extra:
            dbg['table_join_extra'] = len(joined_extra)
            lines.extend(joined_extra)
    return lines


def _parse_line_from_text(txt: str) -> PopLine:
    title = txt
    qty = Decimal("1")
    unit = Decimal("0")
    subtotal = Decimal("0")
    # Buscar cantidad tipo "x 2" o "Cantidad: 2"
    m = re.search(r"(?:x\s*|cantidad\s*:?\s*)(\d{1,4})", txt, flags=re.I)
    if m:
        try:
            qty = Decimal(m.group(1))
        except Exception:
            pass
    # Precio $999,99
    mp = re.search(r"\$\s*([0-9\.,]+)", txt)
    if mp:
        subtotal = _parse_money(mp.group(1))
    # Limpiar título quitando tokens triviales de cantidad/precio
    title = re.sub(r"\$\s*[0-9\.,]+", "", title)
    title = re.sub(r"\b(cantidad|unidades|x)\b\s*:?\s*\d{1,4}", "", title, flags=re.I)
    title = _clean_title_pop(_norm_text(title))
    # Calcular unitario desde subtotal/cantidad si es posible
    if subtotal and qty > 0:
        try:
            unit = (subtotal / qty).quantize(Decimal("0.01"))
        except Exception:
            unit = Decimal("0")
    # clamps de seguridad
    if qty <= 0 or qty >= Decimal('100000'):
        qty = Decimal('1')
    if unit < 0 or unit > Decimal('10000000'):
        unit = Decimal('0')
    # Validar título mínimo POP
    if not _title_is_valid_pop(title):
        title = ''
    return PopLine(title=title, qty=qty, unit_cost=unit, subtotal=(subtotal if subtotal > 0 else None))


def _parse_text(body_text: str, dbg: Dict[str, Any]) -> List[PopLine]:
    lines: List[PopLine] = []
    dropped = 0
    unit_from_subtotal_text = 0
    # Dividir por líneas y filtrar muy cortas
    for raw in (body_text or '').splitlines():
        txt = _norm_text(raw)
        if len(txt) < 4:
            continue
        # Heurística: si la línea tiene al menos 1 palabra y un número, interpretarla
        if re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", txt) and re.search(r"\d", txt):
            ln = _parse_line_from_text(txt)
            if ln.title and _title_is_valid_pop(ln.title):
                if (getattr(ln, 'subtotal', None) or Decimal('0')) > 0 and (ln.unit_cost or Decimal('0')) > 0:
                    unit_from_subtotal_text += 1
                lines.append(ln)
            else:
                dropped += 1
    if dropped:
        dbg['text_lines_dropped'] = dropped
    if unit_from_subtotal_text:
        dbg['unit_from_subtotal_text'] = unit_from_subtotal_text
    return lines


def parse_pop_email(source: bytes | str, kind: str = 'eml') -> PopParsed:
    dbg: Dict[str, Any] = {}
    subject = ''
    rem_date: Optional[str] = None
    body_html = ''
    body_text = ''
    if kind == 'eml':
        subject, rem_date, body_html, body_text = _parse_eml(source if isinstance(source, (bytes, bytearray)) else str(source).encode('utf-8'))
    elif kind == 'html':
        body_html = str(source)
    else:
        body_text = str(source)
    remito_number, _ = _extract_from_subject(subject)
    lines: List[PopLine] = []
    # Helper: texto "plano" para heurísticas (contar "$" y fallback)
    def _to_textish(html: str) -> str:
        try:
            return re.sub(r"<[^>]+>", " ", html)
        except Exception:
            return html

    # Fallback por signos de $: cada línea con $ es probable línea de producto; al total restamos 3 (Subtotal, Total, Ahorro)
    def _fallback_parse_by_dollars(textish: str) -> List[PopLine]:
        out: List[PopLine] = []
        seen: set[str] = set()
        for raw in (textish or '').splitlines():
            t = _norm_text(raw)
            if "$" in t and re.search(r"\$\s*[0-9\.,]+", t) and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", t):
                ln = _parse_line_from_text(t)
                if ln.title and ln.title not in seen and _title_is_valid_pop(ln.title):
                    out.append(ln)
                    seen.add(ln.title)
        return out

    if body_html:
        lines = _parse_html(body_html, dbg)
        if not remito_number:
            # Quick text extraction from HTML to find Pedido 123456
            try:
                # Evitar dependencia directa si no está bs4; usar regex para quitar tags
                textish = _to_textish(body_html)
            except Exception:
                textish = body_html
            remito_number = _extract_from_text_body(_norm_text(textish)) or remito_number
    if not lines and body_text:
        lines = _parse_text(body_text, dbg)
    if not remito_number and body_text:
        remito_number = _extract_from_text_body(_norm_text(body_text)) or remito_number
    # Heurística de conteo por símbolo $ (Subtotal/Total/Ahorro consumen 3)
    text_from_html = _to_textish(body_html) if body_html else ''
    html_dollar_signs = (text_from_html or '').count('$')
    text_dollar_signs = (body_text or '').count('$') if body_text else 0
    dollar_signs = max(html_dollar_signs, text_dollar_signs)
    estimated_lines = max(0, max(html_dollar_signs - 3, text_dollar_signs - 3))
    if html_dollar_signs:
        dbg['html_dollar_signs'] = html_dollar_signs
    if text_dollar_signs:
        dbg['text_dollar_signs'] = text_dollar_signs
    if dollar_signs:
        dbg['dollar_signs'] = dollar_signs
        dbg['estimated_product_lines'] = estimated_lines
    # Si parseamos menos que la estimación, aplicar fallback combinando HTML(textish) y TEXT
    if estimated_lines and len(lines) < estimated_lines:
        extra_html = _fallback_parse_by_dollars(text_from_html)
        extra_text = _fallback_parse_by_dollars(body_text or '') if body_text else []
        extra = []
        if extra_html:
            extra.extend(extra_html)
        if extra_text:
            extra.extend(extra_text)
        if extra:
            # Mezclar sin duplicar por título
            existing = {ln.title for ln in lines}
            added = 0
            unit_from_subtotal_dollar_fallback = 0
            for ln in extra:
                if ln.title and ln.title not in existing:
                    lines.append(ln)
                    existing.add(ln.title)
                    added += 1
                    if (getattr(ln, 'subtotal', None) or Decimal('0')) > 0 and (ln.unit_cost or Decimal('0')) > 0:
                        unit_from_subtotal_dollar_fallback += 1
            if added:
                dbg['fallback_added'] = added
            if unit_from_subtotal_dollar_fallback:
                dbg['unit_from_subtotal_fallback'] = unit_from_subtotal_dollar_fallback
    # Fecha por defecto hoy si no vino
    if not rem_date:
        rem_date = _date.today().isoformat()
    # Generar SKU sintético si falta
    try:
        dt = datetime.fromisoformat(rem_date)
    except Exception:
        try:
            dt = datetime.strptime(rem_date, '%Y-%m-%d')
        except Exception:
            dt = datetime.utcnow()
    base = dt.strftime('POP-%Y%m%d-')
    seq = 1
    for ln in lines:
        if not ln.supplier_sku:
            ln.supplier_sku = f"{base}{seq:03d}"
        seq += 1
    return PopParsed(remito_number=remito_number, remito_date=rem_date, lines=lines, debug=dbg | {'subject': subject, 'has_html': bool(body_html), 'has_text': bool(body_text)})
