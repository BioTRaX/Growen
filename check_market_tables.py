#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: check_market_tables.py
# NG-HEADER: Ubicación: check_market_tables.py
# NG-HEADER: Descripción: Verifica tablas y conteos del dominio Mercado sin exponer credenciales.
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Verifica las tablas del dominio Mercado usando la configuración segura del proyecto."""

import asyncio

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from agent_core.config import settings


async def main() -> None:
    engine = create_async_engine(settings.db_url, future=True)

    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
            tables = sorted(name for name in table_names if name.startswith("market"))

            print("\n=== VERIFICACIÓN DE TABLAS DE MERCADO ===\n")
            if not tables:
                print("No se encontraron tablas del dominio Mercado.")
                return

            print(f"Tablas encontradas: {', '.join(tables)}\n")
            for table in tables:
                quoted_table = connection.dialect.identifier_preparer.quote(table)
                count = await connection.scalar(text(f"SELECT COUNT(*) FROM {quoted_table}"))
                print(f"   {table}: {count:,} registros")
    finally:
        await engine.dispose()

    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
