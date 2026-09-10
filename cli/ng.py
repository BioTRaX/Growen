# NG-HEADER: Nombre de archivo: ng.py
# NG-HEADER: Ubicación: cli/ng.py
# NG-HEADER: Descripción: CLI `ng` con utilidades operativas y diagnósticas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""CLI principal de Growen usando Typer."""
from __future__ import annotations

import asyncio
from pathlib import Path
import yaml
import typer

from services.ingest import loader, mapping as mapping_mod, normalize, upsert
from db.session import SessionLocal
from services.importers.santaplanta_pipeline import parse_remito, ParsedLine  # type: ignore
import uuid
from decimal import Decimal

app = typer.Typer(help="Herramientas de línea de comandos para Growen")
ingest_app = typer.Typer(help="Comandos de ingestión de catálogos")
app.add_typer(ingest_app, name="ingest")
pdf_app = typer.Typer(help="Utilidades de diagnóstico para PDFs de proveedores")
app.add_typer(pdf_app, name="pdf")


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



@pdf_app.command("parse-remito")
def pdf_parse_remito(
    pdf: Path,
    force_ocr: bool = typer.Option(False, help="Forzar OCR (ocrmypdf) antes de intentar el parseo"),
    debug: bool = typer.Option(True, help="Incluir eventos y excerpt en resultado para diagnóstico"),
) -> None:
    """Parsea un remito PDF (Santa Planta) y muestra líneas y validaciones.

    Salida:
    - Remito y Fecha detectados
    - Tabla con: #, SKU, Cant, Unitario, Total, Título (recortado)
    - Resumen: líneas detectadas, expected_items/footer, Importe Total/footer, suma líneas y validaciones
    """
    if not pdf.exists():
        typer.echo(f"No existe el archivo: {pdf}")
        raise typer.Exit(code=2)
    cid = uuid.uuid4().hex
    res = parse_remito(pdf, correlation_id=cid, use_ocr_auto=True, force_ocr=force_ocr, debug=debug)
    typer.echo(f"Remito: {res.remito_number or '-'} | Fecha: {res.remito_date or '-'} | líneas={len(res.lines or [])}")
    # Buscar expectativas del pie
    exp_items = None
    imp_total = None
    for ev in (res.events or []):
        if ev.get("stage") == "footer" and ev.get("event") == "expected_from_footer":
            det = ev.get("details") or {}
            try:
                exp_items = int(det.get("expected_items") or 0) or None
            except Exception:
                exp_items = None
            try:
                v = det.get("importe_total")
                imp_total = Decimal(str(v)) if v is not None else None
            except Exception:
                imp_total = None
            break
    # Imprimir líneas
    def _num(v: Decimal | None) -> str:
        return (f"{v:.2f}" if v is not None else "-")
    total_sum = Decimal("0")
    for i, ln in enumerate(res.lines or [], start=1):
        unit = ln.unit_cost_bonif or Decimal("0")
        tline = (ln.total if (ln.total is not None and ln.total > 0) else (ln.subtotal or (ln.qty * unit)))
        total_sum += (tline or Decimal("0"))
        sku = ln.supplier_sku or "-"
        title = (ln.title or "").strip()
        if len(title) > 80:
            title = title[:77] + "..."
        typer.echo(f"{i:>2}. {sku:>6} | {ln.qty} x {_num(unit)} = {_num(tline)} | {title}")
    # Resumen y validaciones
    typer.echo("")
    if exp_items is not None:
        status_items = "OK" if len(res.lines or []) == exp_items else f"MISMATCH got={len(res.lines or [])}"
        typer.echo(f"Cantidad de Items (footer): {exp_items} -> {status_items}")
    if imp_total is not None:
        diff = abs((total_sum or Decimal("0")) - imp_total)
        ok = diff <= Decimal("0.11")
        typer.echo(f"Importe Total (footer): {imp_total:.2f} | suma líneas: {total_sum:.2f} | diff={diff:.2f} -> {'OK' if ok else 'MISMATCH'}")
    # Clásico
    try:
        cc = getattr(res, "classic_confidence", None)
        if cc is not None:
            typer.echo(f"Confianza clásica: {cc}")
    except Exception:
        pass
    # Nota de eventos relevantes
    sel = [ev for ev in (res.events or []) if ev.get("stage") in {"selection", "fallback", "validation"}]
    if sel:
        typer.echo("\nEventos relevantes:")
        for ev in sel[:8]:
            stage = ev.get("stage"); event = ev.get("event"); details = ev.get("details") or {}
            typer.echo(f" - {stage}:{event} {details}")


if __name__ == "__main__":
    app()
