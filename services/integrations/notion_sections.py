#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: notion_sections.py
# NG-HEADER: Ubicación: services/integrations/notion_sections.py
# NG-HEADER: Descripción: Flujo mínimo de Notion por secciones con subpáginas por reporte
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .notion_client import NotionWrapper, load_notion_settings
import re

LOG = logging.getLogger("services.integrations.notion.sections")


def derive_section_from_url(url: str | None) -> str:
    """Deriva la página padre desde la URL.

    Regla: usar el primer segmento del path como nombre de sección (capitalizado),
    con algunos alias comunes hacia español. La sección "App" se usa sólo para
    la página de inicio (path vacío o "/").
    """
    from urllib.parse import urlparse

    u = (url or "").strip()
    if not u:
        return "App"
    try:
        parsed = urlparse(u)
        path = parsed.path or "/"
    except Exception:
        path = "/"
    # Normalizar
    seg = path.strip("/").split("/")[0] if path and path != "/" else ""
    if not seg:
        return "App"
    slug = seg.lower()
    # Alias conocidos a nombres en español
    alias = {
        "purchases": "Compras",
        "compras": "Compras",
        "stock": "Stock",
        "providers": "Proveedores",
        "proveedores": "Proveedores",
        "products": "Productos",
        "productos": "Productos",
        "admin": "Admin",
        "inicio": "App",
        "home": "App",
    }
    if slug in alias:
        return alias[slug]
    # Default: capitalizar el segmento, reemplazando -/_ por espacio
    name = slug.replace("-", " ").replace("_", " ").strip()
    return name[:1].upper() + name[1:] if name else "App"


def upsert_report_as_child(url: str | None, comment: str, screenshot_path: str | None = None, report_id: str | None = None) -> dict:
    """Crea una subpágina bajo la sección correspondiente con título 'YYYY-MM-DD #N'.

    N = contador del día basado en hijos existentes que comiencen con la fecha.
    Contenido: bloques de texto con screenshot_path (si hay) y comentario.
    """
    cfg = load_notion_settings()
    nw = NotionWrapper()
    if not (cfg.enabled and cfg.errors_db):
        return {"action": "skipped", "reason": "not-enabled", "mode": cfg.mode}
    if cfg.mode != "sections":
        return {"action": "skipped", "reason": "wrong-mode", "mode": cfg.mode}

    # En dry-run devolvemos una simulación sin consultar Notion
    if cfg.dry_run:
        section = derive_section_from_url(url)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        child_title = f"{today} {report_id}" if report_id else f"{today} #1"
        LOG.info("[dry-run] upsert child under '%s' titled '%s' (screenshot=%s)", section, child_title, bool(screenshot_path))
        return {"action": "dry-run", "parent": section, "title": child_title}

    section = derive_section_from_url(url)
    title_prop = nw.get_title_property_name(cfg.errors_db) or "Sección"

    # 1) Buscar página de sección en la DB por título
    parent_page_id = nw.query_db_by_title(cfg.errors_db, title_prop, section)
    if not parent_page_id:
        # Crear fila de sección si no existe (con solo título)
        props = {title_prop: {"title": [{"type": "text", "text": {"content": section}}]}}
        parent_page_id = nw.create_page(cfg.errors_db, props)

    if not parent_page_id:
        return {"action": "error", "reason": "no-parent"}

    # 2) Si el comentario hace referencia a un título existente al inicio de la primera línea,
    #    actualizar esa subpágina en vez de crear una nueva.
    #    Formato esperado: "YYYY-MM-DD br-<digits>".
    first_line = (comment or "").splitlines()[0] if comment else ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+br-\d+\b", first_line.strip(), flags=re.IGNORECASE)
    if m:
        referenced_title = m.group(0)
        # Buscar subpágina hija con ese título exacto bajo la sección
        existing_child = nw.find_child_page_by_title(parent_page_id, referenced_title)
        if existing_child:
            # Construir bloques a anexar
            blocks = []
            if screenshot_path:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": f"screenshot: {screenshot_path}"}}]
                    },
                })
            if comment:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": comment[:1800]}}]
                    },
                })
            ok = nw.append_children(existing_child, blocks) if blocks else True
            return {"action": "updated", "parent": section, "title": referenced_title, "updated": bool(ok)}

    # 3) Armar título hijo para creación
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if report_id:
        child_title = f"{today} {report_id}"
    else:
        children = nw.list_block_children(parent_page_id)
        # Contar hijos cuyo título arranque con 'YYYY-MM-DD'
        count_today = 0
        for ch in children:
            try:
                if ch.get("object") == "page":
                    ch_title = ch.get("properties", {}).get("title", {}).get("title", [])
                    if ch_title and isinstance(ch_title, list):
                        text = ch_title[0].get("plain_text") or ch_title[0].get("text", {}).get("content")
                        if isinstance(text, str) and text.startswith(today):
                            count_today += 1
            except Exception:
                continue
        number = count_today + 1
        child_title = f"{today} #{number}"

    # 4) Construir contenido
    blocks = []
    if screenshot_path:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"screenshot: {screenshot_path}"}}]
            },
        })
    if comment:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": comment[:1800]}}]
            },
        })

    # 5) Crear subpágina
    child_id = nw.create_child_page(parent_page_id, child_title, children_blocks=blocks)
    return {"action": "created", "parent": section, "title": child_title, "child_id": child_id}
