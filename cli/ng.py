"""CLI principal de Growen usando Typer."""
from __future__ import annotations

import asyncio
from pathlib import Path
import yaml
import typer

from services.ingest import loader, mapping as mapping_mod, normalize, upsert
from db.session import SessionLocal

app = typer.Typer(help="Herramientas de línea de comandos para Growen")
ingest_app = typer.Typer(help="Comandos de ingestión de catálogos")
app.add_typer(ingest_app, name="ingest")


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
            await upsert.upsert_rows(
                df.to_dict("records"),
                session,
                mapping_cfg.get("supplier_name", supplier),
                dry_run=dry_run,
            )

    asyncio.run(_run())


if __name__ == "__main__":
    app()
