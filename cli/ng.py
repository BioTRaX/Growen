# NG-HEADER: Nombre de archivo: ng.py
# NG-HEADER: Ubicación: cli/ng.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""CLI principal de Growen usando Typer."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
import yaml
import typer

from services.ingest import loader, mapping as mapping_mod, normalize, upsert
from db.session import SessionLocal
from services.integrations.notion_client import NotionWrapper, load_notion_settings  # type: ignore
from services.integrations.notion_errors import fingerprint_error, ErrorEvent  # type: ignore

app = typer.Typer(help="Herramientas de línea de comandos para Growen")
ingest_app = typer.Typer(help="Comandos de ingestión de catálogos")
app.add_typer(ingest_app, name="ingest")
notion_app = typer.Typer(help="Comandos de integración con Notion")
app.add_typer(notion_app, name="notion")


@app.command()
def db_init() -> None:
    """Inicializa la base de datos ejecutando las migraciones."""
    typer.echo("Aplicando migraciones (simulado)...")


@ingest_app.command("file")
def ingest_file(
    file: Path,
    supplier: str = "default",
    dry_run: bool = False,
) -> None:
    """Ingesta un archivo de catálogo aplicando el mapeo indicado."""
    mapping_path = Path("config/suppliers") / f"{supplier}.yml"
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping_cfg = yaml.safe_load(f)
    df = loader.load_file(file, mapping_cfg)
    df = mapping_mod.map_columns(df, mapping_cfg)
    df = normalize.apply(df, mapping_cfg)

    async def _run() -> None:
        async with SessionLocal() as session:
            if supplier == "santa-planta":
                await upsert.upsert_supplier_rows(
                    df.to_dict("records"), session, supplier, dry_run=dry_run
                )
            else:
                await upsert.upsert_rows(
                    df.to_dict("records"),
                    session,
                    mapping_cfg.get("supplier_name", supplier),
                    dry_run=dry_run,
                )

    asyncio.run(_run())


@ingest_app.command("last")
def ingest_last(apply: bool = False, supplier: str = "santa-planta") -> None:
    """Reprocesa el último archivo subido."""
    uploads_dir = Path("data/uploads")
    files = sorted(uploads_dir.glob("*.xlsx"))
    if not files:
        typer.echo("No hay archivos para procesar")
        return
    file = files[-1]
    ingest_file(file, supplier=supplier, dry_run=not apply)



@notion_app.command("sync-known-errors")
def sync_known_errors(dry_run: bool = True) -> None:
    """Publica patrones de config/known_errors.json como tarjetas base en Notion.

    - Upsert por fingerprint derivado del id del patrón.
    - Settea Estado=Abierto, Frecuencia=0, y copia etiquetas/severidad/servicio sugeridas.
    """
    import json as _json
    from pathlib import Path as _Path

    cfg = load_notion_settings()
    if not (cfg.enabled and cfg.errors_db):
        typer.echo("Notion no habilitado o falta NOTION_ERRORS_DATABASE_ID")
        raise typer.Exit(code=2)
    nw = NotionWrapper()
    h = nw.health()
    if not h.get("has_sdk"):
        typer.echo("Falta paquete notion-client. Instala dependencias primero.")
        raise typer.Exit(code=2)
    # cargar patrones
    p = _Path("config/known_errors.json")
    if not p.exists():
        typer.echo("No existe config/known_errors.json")
        raise typer.Exit(code=2)
    data = _json.loads(p.read_text(encoding="utf-8"))
    patterns = data.get("patterns", []) if isinstance(data, dict) else []
    count = 0
    for pat in patterns:
        pid = str(pat.get("id") or "").strip()
        if not pid:
            continue
        sev = pat.get("severidad") or "Medium"
        servicio = pat.get("servicio") or "api"
        etiquetas = pat.get("etiquetas") or []
        titulo = pat.get("titulo") or pid
        # Fingerprint basado en id del patrón (estable)
        fp = fingerprint_error(
            ErrorEvent(servicio=servicio, entorno=os.getenv("ENV", "dev"), url=None, codigo=pid, mensaje=pid),
            matched={"id": pid},
        )
        # Upsert simple
        page_id = nw.query_by_fingerprint(cfg.errors_db, fp)
        props = {
            "Title": {"title": [{"type": "text", "text": {"content": str(titulo)[:200]}}]},
            "Estado": {"select": {"name": "Abierto"}},
            "Severidad": {"select": {"name": sev}},
            "Servicio": {"select": {"name": servicio}},
            "Entorno": {"select": {"name": os.getenv("ENV", "dev")}},
            "Fingerprint": {"rich_text": [{"type": "text", "text": {"content": fp}}]},
            "Mensaje": {"rich_text": [{"type": "text", "text": {"content": f"Patrón base: {pid}"}}]},
            "Código": {"rich_text": [{"type": "text", "text": {"content": pid}}]},
            "Etiquetas": {"multi_select": [{"name": t} for t in etiquetas[:10]]},
            "FirstSeen": {"date": {"start": datetime.utcnow().isoformat()}},
            "LastSeen": {"date": {"start": datetime.utcnow().isoformat()}},
        }
        if dry_run or cfg.dry_run:
            typer.echo(f"[dry-run] upsert {pid} fp={fp} {'(update)' if page_id else '(create)'}")
        else:
            if page_id:
                nw.update_page(page_id, {k: v for k, v in props.items() if k in {"Severidad", "LastSeen", "Etiquetas"}})
            else:
                nw.create_page(cfg.errors_db, props)
        count += 1
    typer.echo(f"Listo: {count} patrones procesados")


@notion_app.command("validate-db")
def notion_validate_db() -> None:
    """Valida que la base de Notion de errores tenga propiedades requeridas.

    Requisitos mínimos por nombre (case sensitive):
    - Title (title)
    - Estado (select)
    - Severidad (select)
    - Servicio (select)
    - Entorno (select)
    - Sección (select)
    - Fingerprint (rich_text)
    - Mensaje (rich_text)
    - Código (rich_text)
    - FirstSeen (date)
    - LastSeen (date)
    - Etiquetas (multi_select)
    """
    cfg = load_notion_settings()
    if not (cfg.enabled and cfg.errors_db):
        typer.echo("Notion no habilitado o falta NOTION_ERRORS_DATABASE_ID")
        raise typer.Exit(code=2)
    nw = NotionWrapper()
    meta = nw.retrieve_database(cfg.errors_db)
    if not meta:
        typer.echo("No se pudo leer la base de Notion. Verifica API key/ID.")
        raise typer.Exit(code=2)
    props = meta.get("properties", {}) if isinstance(meta, dict) else {}
    # Modo sections: sólo requerimos que exista alguna propiedad de tipo title
    if cfg.mode == "sections":
        title_name = None
        if isinstance(props, dict):
            for name, p in props.items():
                if isinstance(p, dict) and p.get("type") == "title":
                    title_name = name
                    break
        if title_name:
            # Verificar existencia de páginas base de sección
            nw = NotionWrapper()
            missing_sections: list[str] = []
            for section in ("Compras", "Stock", "App"):
                page_id = nw.query_db_by_title(cfg.errors_db, title_name, section)  # type: ignore[arg-type]
                if not page_id:
                    missing_sections.append(section)
            if missing_sections:
                typer.echo(
                    "Advertencia: faltan páginas base en Notion (se crean on-demand): "
                    + ", ".join(missing_sections)
                )
            typer.echo(f"OK: modo sections con propiedad de título '{title_name}'.")
            raise typer.Exit(code=0)
        else:
            typer.echo("Falta una propiedad de tipo 'title' en la DB.")
            raise typer.Exit(code=1)
    else:
        # Modo cards: validar esquema extendido como antes
        expected = {
            "Title": "title",
            "Estado": "select",
            "Severidad": "select",
            "Servicio": "select",
            "Entorno": "select",
            "Sección": "select",
            "Fingerprint": "rich_text",
            "Mensaje": "rich_text",
            "Código": "rich_text",
            "FirstSeen": "date",
            "LastSeen": "date",
            "Etiquetas": "multi_select",
        }
        missing: list[str] = []
        wrong_type: list[str] = []
        for name, typ in expected.items():
            p = props.get(name)
            if not p:
                missing.append(name)
                continue
            pt = p.get("type")
            if pt != typ:
                wrong_type.append(f"{name} (esperado {typ}, actual {pt})")
        if not missing and not wrong_type:
            typer.echo("OK: esquema mínimo válido.")
        else:
            if missing:
                typer.echo("Faltan propiedades: " + ", ".join(missing))
            if wrong_type:
                typer.echo("Tipos incorrectos: " + ", ".join(wrong_type))
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
