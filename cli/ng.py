"""CLI principal de Growen usando Typer."""
from __future__ import annotations

import typer

app = typer.Typer(help="Herramientas de línea de comandos para Growen")


@app.command()
def db_init() -> None:
    """Inicializa la base de datos ejecutando las migraciones."""
    typer.echo("Aplicando migraciones (simulado)...")


if __name__ == "__main__":
    app()
