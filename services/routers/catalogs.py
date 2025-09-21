# NG-HEADER: Nombre de archivo: catalogs.py
# NG-HEADER: Ubicación: services/routers/catalogs.py
# NG-HEADER: Descripción: Endpoints para generación y acceso a catálogo PDF.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import logging
import json
from datetime import datetime
import os
from pathlib import Path
from typing import List, Dict, Any
import re
import html as html_mod
import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, Image, Category
from db.session import get_session
from services.auth import require_roles, require_csrf, current_session, SessionData

logger = logging.getLogger("growen.catalogs")

router = APIRouter(prefix="/catalogs", tags=["catalogs"])

CATALOG_DIR = Path("./catalogos").resolve()
PDF_PATH = CATALOG_DIR / "ultimo_catalogo.pdf"
LOG_DIR = Path("./logs/catalogs").resolve()
DETAIL_LOG_DIR = LOG_DIR / "detail"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DETAIL_LOG_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

RETENTION = int(os.getenv("CATALOG_RETENTION", "0") or 0)  # 0 = ilimitado


class CatalogGenerateIn(BaseModel):
    ids: List[int]


def _category_root(cat_map: Dict[int, Category], category_id: int | None) -> str:
    if not category_id:
        return "Sin categoría"
    seen = set()
    current = category_id
    name = None
    while current and current not in seen:
        seen.add(current)
        cat = cat_map.get(current)
        if not cat:
            break
        name = cat.name
        if cat.parent_id is None:
            break
        current = cat.parent_id
    return name or "Sin categoría"


def _build_html(groups: Dict[str, list[dict[str, Any]]]) -> str:
    css = """
    <style>
    body { font-family: 'Helvetica','Arial',sans-serif; background:#111; color:#eee; margin:0; padding:32px; }
    h1 { color:#f0f; text-align:center; margin-top:0; }
    h2 { color:#22c55e; border-bottom:1px solid #333; padding-bottom:4px; margin-top:40px; }
    .cat-list { columns:2; column-gap:40px; }
    .cat-item { break-inside:avoid; margin:2px 0; font-size:14px; }
    .price { color:#f0f; font-weight:600; }
    .grid-page { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:28px; page-break-after:always; padding:16px 0; }
    .card { background:#1d1d1d; border:1px solid #333; border-radius:8px; padding:12px; display:flex; flex-direction:column; }
    .card h3 { margin:4px 0 8px; font-size:16px; line-height:1.2; color:#fff; }
    .card img { max-width:100%; max-height:180px; object-fit:contain; margin:0 auto 8px; filter: drop-shadow(0 0 4px #000); }
    .desc { font-size:12px; line-height:1.35; color:#bbb; margin-top:auto; white-space:pre-wrap; }
    footer { text-align:center; font-size:10px; color:#666; margin-top:60px; }
    @page { size:A4; margin:20mm 15mm; background:#111; }
    </style>
    """
    # Listado por categoría
    parts = ["<html><head>", css, "</head><body>"]
    parts.append("<h1>Catálogo</h1><section id='listado'>")
    for cat in sorted(groups.keys()):
        items = groups[cat]
        parts.append(f"<h2>{cat}</h2><div class='cat-list'>")
        for p in items:
            price = f"<span class='price'>$ {p['price']:.2f}</span>" if p.get("price") is not None else ""
            parts.append(f"<div class='cat-item'>{p['title']} {price}</div>")
        parts.append("</div>")
    parts.append("</section><section id='fichas'>")
    # Fichas (no mezclar categorías en misma página)
    for cat in sorted(groups.keys()):
        items = groups[cat]
        # slice each 4
        for i in range(0, len(items), 4):
            chunk = items[i:i+4]
            parts.append("<div class='grid-page'>")
            for p in chunk:
                img_html = f"<img src='{p['image']}' alt='img'/>" if p.get("image") else ""
                desc = (p.get("description") or "").strip()
                if len(desc) > 600:
                    desc = desc[:600] + "…"
                price = f"<div class='price'>$ {p['price']:.2f}</div>" if p.get("price") is not None else ""
                parts.append("<div class='card'>" + img_html + f"<h3>{p['title']}</h3>{price}<div class='desc'>{desc}</div></div>")
            parts.append("</div>")
    parts.append("</section><footer>Generado: " + datetime.utcnow().isoformat() + " UTC</footer></body></html>")
    return "".join(parts)


def _render_pdf(html: str) -> bytes:
    # Prefer WeasyPrint
    try:
        from weasyprint import HTML  # type: ignore
        return HTML(string=html).write_pdf()
    except Exception:  # pragma: no cover - fallback
        try:
            # Minimal fallback with reportlab: render plain text (degraded)
            from reportlab.lib.pagesizes import A4  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
            from io import BytesIO
            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            text = c.beginText(40, A4[1]-40)
            text.textLine("Catálogo (fallback texto)")
            for line in html.splitlines():
                if len(line) > 100:
                    line = line[:100]
                text.textLine(line)
                if text.getY() < 60:
                    c.drawText(text)
                    c.showPage()
                    text = c.beginText(40, A4[1]-40)
            c.drawText(text)
            c.showPage()
            c.save()
            return buf.getvalue()
        except Exception as e:  # pragma: no cover
            logger.exception("Fallo render PDF fallback: %s", e)
            raise HTTPException(500, detail="No se pudo generar el PDF")


MAX_DETAIL_LOGS = 40  # cantidad máxima de logs detallados que se conservan
# Estado actual de generación en memoria
_active_generation: dict[str, Any] = {"running": False, "started_at": None, "ids": 0}
# Timeout automático para limpieza del lock (segundos). Por defecto 15 minutos.
try:
    CATALOG_LOCK_TIMEOUT = int(os.getenv("CATALOG_LOCK_TIMEOUT", "900"))
except Exception:
    CATALOG_LOCK_TIMEOUT = 900

def _maybe_expire_lock() -> None:
    """Si hay un lock activo y superó el timeout, liberarlo automáticamente."""
    if not _active_generation.get("running"):
        return
    if not _active_generation.get("started_at"):
        return
    try:
        started = datetime.fromisoformat(_active_generation["started_at"])  # type: ignore[arg-type]
        age = (datetime.utcnow() - started).total_seconds()
        if CATALOG_LOCK_TIMEOUT > 0 and age > CATALOG_LOCK_TIMEOUT:
            logger.warning("[catalog] lock expired automatically after %.0fs (timeout=%ss)", age, CATALOG_LOCK_TIMEOUT)
            _active_generation.update({"running": False})
    except Exception:
        # Si falla el parseo, no romper el flujo; logear y no hacer nada
        logger.exception("[catalog] error checking lock timeout")


def _clean_old_logs():
    try:
        detail_files = sorted(DETAIL_LOG_DIR.glob("catalog_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in detail_files[MAX_DETAIL_LOGS:]:
            f.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        logger.exception("No se pudieron limpiar logs detallados antiguos")


def _catalog_filename(ts: datetime) -> str:
    return f"catalog_{ts.strftime('%Y%m%d_%H%M%S')}.pdf"


def _list_catalog_files() -> list[Path]:
    files = [p for p in CATALOG_DIR.glob("catalog_*.pdf") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _apply_retention():
    if RETENTION and RETENTION > 0:
        files = _list_catalog_files()
        for p in files[RETENTION:]:
            try:
                p.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass


@router.post("/generate", dependencies=[Depends(require_roles("admin", "colaborador")), Depends(require_csrf)])
async def generate_catalog(data: CatalogGenerateIn, session: AsyncSession = Depends(get_session), session_data: SessionData = Depends(current_session)):
    _maybe_expire_lock()
    if not data.ids:
        raise HTTPException(400, detail="No hay productos seleccionados")
    if _active_generation["running"]:
        raise HTTPException(409, detail="Ya hay una generación en curso")
    _active_generation.update({"running": True, "started_at": datetime.utcnow().isoformat(), "ids": len(data.ids)})
    start_ts = datetime.utcnow()
    logger.info("[catalog] start ids=%d user=%s", len(data.ids), getattr(session_data.user, 'id', None))
    detail_lines: list[str] = []
    def log_step(msg: str, **extra):
        line = {"ts": datetime.utcnow().isoformat(), "step": msg, **extra}
        detail_lines.append(json.dumps(line, ensure_ascii=False))
        logger.debug("[catalog] %s %s", msg, extra)
    log_step("start", count=len(data.ids), user=getattr(session_data.user, 'id', None))
    # Cargar productos
    # Eager-load variants to avoid async lazy-load (MissingGreenlet)
    q = select(Product).options(selectinload(Product.variants)).where(Product.id.in_(data.ids))
    products = (await session.execute(q)).scalars().all()
    if not products:
        _active_generation.update({"running": False})
        raise HTTPException(404, detail="Productos no encontrados")
    log_step("products_loaded", products=len(products))
    # Cargar imágenes primarias
    img_q = select(Image).where(Image.product_id.in_([p.id for p in products]), Image.active == True).order_by(Image.is_primary.desc(), Image.sort_order.asc().nulls_last())
    images = (await session.execute(img_q)).scalars().all()
    log_step("images_loaded", images=len(images))
    img_map: Dict[int, str] = {}
    for img in images:
        if img.product_id not in img_map:
            img_map[img.product_id] = img.url or img.path or ""
    # Cargar categorías referenciadas
    cat_ids = {p.category_id for p in products if p.category_id}
    cats = []
    if cat_ids:
        cats = (await session.execute(select(Category).where(Category.id.in_(cat_ids)))).scalars().all()
    cat_map = {c.id: c for c in cats}
    # Armar estructura agrupada
    groups: Dict[str, list[dict[str, Any]]] = {}
    # Preparar función de sanitizado básico (descripcion "blanda")
    tag_re = re.compile(r"<[^>]+>")
    def _soft_description(raw: str | None) -> str:
        if not raw:
            return ""
        txt = raw.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        txt = tag_re.sub("", txt)
        txt = html_mod.unescape(txt)
        # normalizar espacios y cortar
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) > 1000:
            txt = txt[:1000] + "…"
        return txt

    for p in products:
        root = _category_root(cat_map, p.category_id)
        # Determinar precio de venta: atributo directo `sale_price` en Product (si existe), si no variantes.
        price = getattr(p, 'sale_price', None)
        if price is None:
            # Usar la variante con promo_price si disponible, sino price mínima.
            variants = getattr(p, 'variants', []) or []
            cand = []
            for v in variants:
                if getattr(v, 'promo_price', None) is not None:
                    cand.append(getattr(v, 'promo_price'))
                elif getattr(v, 'price', None) is not None:
                    cand.append(getattr(v, 'price'))
            if cand:
                try:
                    price = float(min(cand))
                except Exception:
                    price = None
        entry = {
            "id": p.id,
            "title": p.title,
            "price": float(price) if price is not None else None,
            "image": img_map.get(p.id),
            "description": _soft_description(getattr(p, 'description_html', None)),
        }
        groups.setdefault(root, []).append(entry)
    # Ordenar items alfabéticamente por título
    for lst in groups.values():
        lst.sort(key=lambda x: x["title"].lower())
    log_step("groups_built", groups=len(groups))
    html = _build_html(groups)
    log_step("html_built", size=len(html))
    pdf_bytes = _render_pdf(html)
    log_step("pdf_rendered", bytes=len(pdf_bytes))
    ts = datetime.utcnow()
    fname = _catalog_filename(ts)
    target = CATALOG_DIR / fname
    target.write_bytes(pdf_bytes)
    log_step("pdf_written", file=fname, bytes=len(pdf_bytes))
    # Actualizar alias latest
    try:
        if PDF_PATH.exists():
            PDF_PATH.unlink()
        # Crear symlink si el SO lo permite, sino copiar
        try:
            PDF_PATH.symlink_to(target.name)  # relative symlink inside dir
        except Exception:
            # fallback copy
            PDF_PATH.write_bytes(pdf_bytes)
        log_step("latest_updated", mode="symlink" if PDF_PATH.is_symlink() else "copy")
    except Exception:
        logger.exception("No se pudo actualizar ultimo_catalogo.pdf")
        log_step("latest_update_failed")
    _apply_retention()
    log_step("retention_applied")
    dur_ms = int((datetime.utcnow() - start_ts).total_seconds() * 1000)
    logger.info("[catalog] ok file=%s size=%dB dur_ms=%d", target, len(pdf_bytes), dur_ms)
    # Generar resumen simple de logs antes de limpiar
    try:
        summary = {"generated_at": ts.isoformat(), "file": fname, "size": len(pdf_bytes), "count": len(products), "duration_ms": dur_ms}
        (LOG_DIR / f"summary_{ts.strftime('%Y%m%d_%H%M%S')}.json").write_text(__import__('json').dumps(summary, ensure_ascii=False, indent=2))
        log_step("summary_written")
    except Exception:
        logger.exception("No se pudo escribir summary de catálogo")
    # Persistir log detallado
    try:
        (DETAIL_LOG_DIR / f"{fname.replace('.pdf','')}.log").write_text("\n".join(detail_lines), encoding="utf-8")
    except Exception:
        logger.exception("No se pudo escribir log detallado de catálogo")
    _clean_old_logs()
    _active_generation.update({"running": False})
    return {
        "message": "ok",
        "generated_at": ts.isoformat(),
        "count": len(products),
        "id": fname.removeprefix("catalog_").removesuffix(".pdf"),
        "filename": fname,
        "size": len(pdf_bytes),
    }


@router.get("", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def list_catalogs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    from_dt: str | None = Query(None, description="Fecha desde YYYY-MM-DD"),
    to_dt: str | None = Query(None, description="Fecha hasta YYYY-MM-DD"),
):
    def _parse_catalog_dt(id_part: str) -> datetime | None:
        try:
            return datetime.strptime(id_part, "%Y%m%d_%H%M%S")
        except Exception:
            return None
    all_rows = []
    from_ts = None
    to_ts = None
    if from_dt:
        try:
            from_ts = datetime.strptime(from_dt, "%Y-%m-%d")
        except Exception:
            raise HTTPException(400, detail="from_dt inválido (YYYY-MM-DD)")
    if to_dt:
        try:
            to_ts = datetime.strptime(to_dt, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except Exception:
            raise HTTPException(400, detail="to_dt inválido (YYYY-MM-DD)")
    for p in _list_catalog_files():
        ts_part = p.stem.replace("catalog_", "")
        dt = _parse_catalog_dt(ts_part)
        if dt is None:
            continue
        if from_ts and dt < from_ts:
            continue
        if to_ts and dt > to_ts:
            continue
        all_rows.append({
            "id": ts_part,
            "filename": p.name,
            "size": p.stat().st_size,
            "modified_at": dt.isoformat() + "Z",
            "latest": PDF_PATH.exists() and (PDF_PATH.is_symlink() and PDF_PATH.resolve() == p or (not PDF_PATH.is_symlink() and PDF_PATH.read_bytes() == p.read_bytes())),
        })
    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    paged = all_rows[start:end]
    pages = (total + page_size - 1) // page_size if page_size else 1
    return {"items": paged, "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.get("/export.csv", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def export_catalogs_csv(
    from_dt: str | None = Query(None, description="Fecha desde YYYY-MM-DD"),
    to_dt: str | None = Query(None, description="Fecha hasta YYYY-MM-DD"),
):
    def _parse_catalog_dt(id_part: str) -> datetime | None:
        try:
            return datetime.strptime(id_part, "%Y%m%d_%H%M%S")
        except Exception:
            return None
    from_ts = None
    to_ts = None
    if from_dt:
        try:
            from_ts = datetime.strptime(from_dt, "%Y-%m-%d")
        except Exception:
            raise HTTPException(400, detail="from_dt inválido (YYYY-MM-DD)")
    if to_dt:
        try:
            to_ts = datetime.strptime(to_dt, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except Exception:
            raise HTTPException(400, detail="to_dt inválido (YYYY-MM-DD)")
    rows: list[dict[str, Any]] = []
    for p in _list_catalog_files():
        ts_part = p.stem.replace("catalog_", "")
        dt = _parse_catalog_dt(ts_part)
        if dt is None:
            continue
        if from_ts and dt < from_ts:
            continue
        if to_ts and dt > to_ts:
            continue
        rows.append({
            "id": ts_part,
            "filename": p.name,
            "size": p.stat().st_size,
            "modified_at": dt.isoformat() + "Z",
            "latest": PDF_PATH.exists() and (PDF_PATH.is_symlink() and PDF_PATH.resolve() == p or (not PDF_PATH.is_symlink() and PDF_PATH.read_bytes() == p.read_bytes())),
        })
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["id", "filename", "size", "modified_at", "latest"])
    for r in rows:
        writer.writerow([r["id"], r["filename"], r["size"], r["modified_at"], int(bool(r["latest"]))])
    content = si.getvalue().encode()
    return StreamingResponse(iter([content]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=catalogs_export.csv"})


def _catalog_path_from_id(catalog_id: str) -> Path:
    # basic validation
    if not catalog_id or len(catalog_id) != 15:  # YYYYMMDD_HHMMSS
        raise HTTPException(400, detail="ID inválido")
    fname = f"catalog_{catalog_id}.pdf"
    path = CATALOG_DIR / fname
    if not path.exists():
        raise HTTPException(404, detail="Catálogo no encontrado")
    return path


@router.get("/{catalog_id}", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def view_catalog(catalog_id: str):
    path = _catalog_path_from_id(catalog_id)
    return FileResponse(str(path), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{path.name}"'})


@router.delete("/{catalog_id}", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def delete_catalog(catalog_id: str):
    path = _catalog_path_from_id(catalog_id)
    try:
        path.unlink()
    except Exception:
        raise HTTPException(500, detail="No se pudo eliminar el catálogo")
    # Si el eliminado era el apuntado por latest, recalcular
    try:
        if PDF_PATH.exists():
            # Resolver target actual
            target_same = False
            if PDF_PATH.is_symlink():
                try:
                    target_same = PDF_PATH.resolve() == path
                except Exception:
                    target_same = False
            else:
                try:
                    target_same = PDF_PATH.read_bytes() == path.read_bytes()
                except Exception:
                    target_same = False
            if target_same:
                PDF_PATH.unlink(missing_ok=True)  # type: ignore[arg-type]
                remaining = _list_catalog_files()
                if remaining:
                    new_latest = remaining[0]
                    try:
                        PDF_PATH.symlink_to(new_latest.name)
                    except Exception:
                        PDF_PATH.write_bytes(new_latest.read_bytes())
    except Exception:
        logger.exception("Fallo al recalcular latest tras delete")
    return {"deleted": catalog_id}


@router.head("/{catalog_id}", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def head_catalog(catalog_id: str):
    _catalog_path_from_id(catalog_id)
    return {}


@router.get("/{catalog_id}/download", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def download_catalog(catalog_id: str):
    path = _catalog_path_from_id(catalog_id)
    return FileResponse(str(path), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{path.name}"'})


@router.get("/latest", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def view_latest():
    if not PDF_PATH.exists():
        raise HTTPException(404, detail="Catálogo no encontrado")
    return FileResponse(str(PDF_PATH), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="ultimo_catalogo.pdf"'})


@router.head("/latest", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def head_latest():
    if not PDF_PATH.exists():
        raise HTTPException(404, detail="Catálogo no encontrado")
    return {}


@router.get("/latest/download", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def download_latest():
    if not PDF_PATH.exists():
        raise HTTPException(404, detail="Catálogo no encontrado")
    return FileResponse(str(PDF_PATH), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="ultimo_catalogo.pdf"'})


# ---- Diagnóstico ----

@router.get("/diagnostics/status", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def catalog_status():
    _maybe_expire_lock()
    return {
        "active_generation": _active_generation,
        "detail_logs": len(list(DETAIL_LOG_DIR.glob('catalog_*.log'))),
        "summaries": len(list(LOG_DIR.glob('summary_*.json')))
    }


@router.get("/diagnostics/config", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def catalog_config():
    """Devuelve configuración efectiva de diagnósticos (timeout de lock)."""
    source = "env" if os.getenv("CATALOG_LOCK_TIMEOUT") else "default"
    return {"lock_timeout_s": int(CATALOG_LOCK_TIMEOUT), "source": source}


@router.post("/diagnostics/unlock", dependencies=[Depends(require_roles("admin")), Depends(require_csrf)])
async def catalog_unlock():
    """Desbloquea manualmente el estado de generación de catálogo.

    Útil si una generación falló y dejó el flag en memoria activo. No cancela trabajos reales,
    sólo limpia el marcador en memoria. Registrar en logs para auditoría.
    """
    prev = dict(_active_generation)
    _active_generation.update({"running": False})
    logger.warning("[catalog] unlock requested: %s -> %s", prev, _active_generation)
    return {"status": "unlocked", "previous": prev, "active_generation": _active_generation}


@router.get("/diagnostics/summaries", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def catalog_summaries(limit: int = Query(20, ge=1, le=200)):
    _maybe_expire_lock()
    files = sorted(LOG_DIR.glob('summary_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    data = []
    for f in files:
        try:
            data.append(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            data.append({"file": f.name, "error": "parse_error"})
    return {"items": data, "total": len(data)}


@router.get("/diagnostics/log/{catalog_id}", dependencies=[Depends(require_roles("admin", "colaborador"))])
async def catalog_detail_log(catalog_id: str):
    # catalog_id formato YYYYMMDD_HHMMSS
    if not catalog_id or len(catalog_id) != 15:
        raise HTTPException(400, detail="ID inválido")
    log_path = DETAIL_LOG_DIR / f"catalog_{catalog_id}.log"
    if not log_path.exists():
        raise HTTPException(404, detail="Log no encontrado")
    lines = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        try:
            lines.append(json.loads(line))
        except Exception:
            lines.append({"raw": line})
    return {"items": lines, "count": len(lines)}
