"""CLI principal del proyecto."""

import csv
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select, func

from agent_core import settings
from agent_core.db import Base, engine, get_session
from agent_core.models import Product, Variant, Inventory, Image

app = typer.Typer()


def get_alembic_config() -> Config:
    """Obtiene la configuración de Alembic."""
    cfg = Config(str(Path(__file__).resolve().parent.parent / "infra" / "alembic.ini"))
    return cfg


@app.command()
def version() -> None:
    """Muestra la versión de la aplicación."""
    typer.echo("Growen CLI")


db_app = typer.Typer(help="Comandos relacionados con la base de datos")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init() -> None:
    """Ejecuta migraciones para inicializar la base de datos."""
    cfg = get_alembic_config()
    command.upgrade(cfg, "head")
    typer.echo("Migraciones aplicadas")


@db_app.command("drop")
def db_drop(force: bool = typer.Option(False, "--force", help="Omitir confirmación")) -> None:
    """Elimina todas las tablas (solo modo dev)."""
    if settings.env != "dev":
        typer.echo("Operación permitida solo en entorno de desarrollo")
        raise typer.Exit(1)
    if force or typer.confirm("¿Seguro que quieres eliminar todas las tablas?"):
        Base.metadata.drop_all(bind=engine)
        typer.echo("Tablas eliminadas")


@db_app.command("info")
def db_info() -> None:
    """Muestra la cantidad de registros por tabla."""
    with get_session() as session:
        products = session.scalar(select(func.count(Product.id))) or 0
        variants = session.scalar(select(func.count(Variant.id))) or 0
        images = session.scalar(select(func.count(Image.id))) or 0
        inventory = session.scalar(select(func.count(Inventory.id))) or 0
    typer.echo(f"products: {products}")
    typer.echo(f"variants: {variants}")
    typer.echo(f"images: {images}")
    typer.echo(f"inventory: {inventory}")


catalog_app = typer.Typer(help="Operaciones con el catálogo")
app.add_typer(catalog_app, name="catalog")


@catalog_app.command("export")
def catalog_export(out: Path = typer.Option(..., "--out", help="Archivo CSV de salida")) -> None:
    """Exporta productos con variantes e inventario a CSV."""
    with get_session() as session:
        img_subq = (
            select(Image.url)
            .where(Image.product_id == Product.id)
            .order_by(Image.sort_order)
            .limit(1)
            .scalar_subquery()
        )

        query = (
            select(
                Product.id,
                Product.slug,
                Product.title,
                Variant.sku,
                Variant.price,
                Inventory.stock_qty,
                img_subq.label("image_url"),
            )
            .join(Variant, Variant.product_id == Product.id)
            .join(Inventory, Inventory.variant_id == Variant.id, isouter=True)
        )

        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    "product_id",
                    "product_slug",
                    "product_title",
                    "variant_sku",
                    "variant_price",
                    "stock_qty",
                    "image_url",
                ]
            )
            for row in session.execute(query):
                writer.writerow(row)
    typer.echo(f"Catálogo exportado a {out}")


if __name__ == "__main__":
    app()
