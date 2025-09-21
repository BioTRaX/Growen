#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: notion_errors.py
# NG-HEADER: Ubicación: services/integrations/notion_errors.py
# NG-HEADER: Descripción: Servicio para crear/actualizar tarjetas de errores conocidos en Notion
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import json
import re
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .notion_client import NotionWrapper, load_notion_settings

LOG = logging.getLogger("services.integrations.notion.errors")


@dataclass
class ErrorEvent:
    servicio: str
    entorno: str
    url: Optional[str]
    codigo: Optional[str]  # clase de excepción o código de error
    mensaje: str
    stacktrace: Optional[str] = None
    correlation_id: Optional[str] = None
    etiquetas: Optional[list[str]] = None
    when: datetime = datetime.utcnow()
    seccion: Optional[str] = None  # Compras | Stock | Productos (u otros)


def _load_patterns() -> list[dict]:
    cfg_path = Path("config/known_errors.json")
    if not cfg_path.exists():
        return []
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8")) .get("patterns", [])
    except Exception:
        LOG.exception("No se pudo leer known_errors.json")
        return []


def match_known_error(ev: ErrorEvent) -> Optional[dict]:
    text = f"{ev.codigo or ''}\n{ev.mensaje or ''}\n{ev.stacktrace or ''}\n{ev.url or ''}"
    patterns = _load_patterns()
    for pat in patterns:
        try:
            if re.search(pat.get("regex", ""), text, flags=re.IGNORECASE):
                return pat
        except re.error:
            LOG.warning("Regex inválido en known_errors.json: %s", pat)
            continue
    return None


def fingerprint_error(ev: ErrorEvent, matched: Optional[dict]) -> str:
    parts = [
        matched.get("id") if matched else None,
        ev.servicio,
        (ev.codigo or "").strip(),
        (ev.mensaje or "").strip().splitlines()[0][:160],
        (ev.url or "").split("?")[0][:160],  # normalizar URL sin query
    ]
    base = "|".join(x or "" for x in parts)
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()


def _now_iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.utcnow()).isoformat()


def _notion_props_from_event(ev: ErrorEvent, matched: Optional[dict], fingerprint: str) -> Dict[str, Any]:
    titulo = (matched.get("titulo") if matched else None) or (ev.codigo or "Error")
    sev = (matched.get("severidad") if matched else None) or "Medium"
    tags = list({*(matched.get("etiquetas") or []), *(ev.etiquetas or [])})
    sec = _derive_section(ev)
    # Propiedades Notion (formato SDK)
    return {
        "Title": {"title": [{"type": "text", "text": {"content": str(titulo)[:200]}}]},
        "Estado": {"select": {"name": "Abierto"}},
        "Severidad": {"select": {"name": sev}},
        "Servicio": {"select": {"name": ev.servicio}},
        "Entorno": {"select": {"name": ev.entorno}},
        "Sección": {"select": {"name": sec}},
        "Fingerprint": {"rich_text": [{"type": "text", "text": {"content": fingerprint}}]},
        "Mensaje": {"rich_text": [{"type": "text", "text": {"content": ev.mensaje[:1800]}}]},
        "Código": {"rich_text": [{"type": "text", "text": {"content": (ev.codigo or "")[:200]}}]},
        "URL": {"url": (ev.url or None)},
        "FirstSeen": {"date": {"start": _now_iso(ev.when)}},
        "LastSeen": {"date": {"start": _now_iso()}},
        "Etiquetas": {"multi_select": [{"name": t} for t in tags[:10]]},
        # Campos extendidos (si existen en la DB):
        "Stacktrace": {"rich_text": [{"type": "text", "text": {"content": (ev.stacktrace or "")[:1800]}}]},
        "CorrelationId": {"rich_text": [{"type": "text", "text": {"content": (ev.correlation_id or "")[:200]}}]},
    }


def _derive_section(ev: ErrorEvent) -> str:
    if ev.seccion:
        return ev.seccion
    u = (ev.url or "").lower()
    svc = (ev.servicio or "").lower()
    # Heurísticas por URL
    if any(x in u for x in ["/compras", "/purchases", "/purchases/"]):
        return "Compras"
    if any(x in u for x in ["/stock", "/inventario", "/inventory"]):
        return "Stock"
    if any(x in u for x in ["/productos", "/products", "/catalog"]):
        return "Productos"
    # Heurísticas por servicio
    if svc in {"purchases", "import_pdf"}:
        return "Compras"
    if svc in {"stock"}:
        return "Stock"
    if svc in {"products", "catalog"}:
        return "Productos"
    return "General"


def create_or_update_card(ev: ErrorEvent) -> dict:
    """Upsert por fingerprint. Si existe, actualiza LastSeen y (opcional) contador.
    Devuelve dict con action, fingerprint y page_id (si aplica).
    """
    cfg = load_notion_settings()
    nw = NotionWrapper()
    health = nw.health()
    if not (cfg.enabled and cfg.errors_db):
        return {"action": "skipped", "reason": "not-enabled", "health": health}

    matched = match_known_error(ev)
    fp = fingerprint_error(ev, matched)
    props = _notion_props_from_event(ev, matched, fp)

    try:
        page_id = nw.query_by_fingerprint(cfg.errors_db, fp)
        if page_id:
            ok = nw.update_page(page_id, {
                # actualizar sólo campos volátiles
                "LastSeen": props["LastSeen"],
            })
            return {"action": "updated", "fingerprint": fp, "page_id": page_id, "ok": ok}
        else:
            page_id = nw.create_page(cfg.errors_db, props)
            return {"action": "created", "fingerprint": fp, "page_id": page_id}
    except Exception as e:  # pragma: no cover
        LOG.exception("Fallo upsert de tarjeta Notion: %s", e)
        return {"action": "error", "fingerprint": fp, "error": str(e)}
