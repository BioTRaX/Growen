#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250927_consolidated_base.py
# NG-HEADER: Ubicación: db/migrations/versions/20250927_consolidated_base.py
# NG-HEADER: Descripción: Migración de consolidación inicial (snapshot esquema actual)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Consolidated base schema snapshot

Motivación:
    Unificar historial disperso de migraciones (heads y merges previos) en un
    único snapshot que pueda recrear el estado estable actual sin depender
    de cadenas largas con parches idempotentes.

Alcance:
    - No elimina migraciones anteriores (sirven para históricos / auditoría).
    - Reproduce tablas e índices principales mediante Base.metadata.create_all.
    - Incluye guard clauses para no sobre-escribir objetos existentes.

Downgrade:
    - No intenta revertir a estado previo (riesgo de pérdida de datos). Se
      deja como noop explícito.

Advertencia:
    - Este archivo debe permanecer sincronizado con el estado inmediatamente
      posterior a su creación. Cambios posteriores en modelos requieren nuevas
      migraciones incrementales normales.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from db.base import Base  # type: ignore

# Revisiones Alembic
revision = "20250927_consolidated_base"
down_revision = "20250927_merge_deprecated_stock_ledger_heads"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Revisión rápida: si existe una tabla clave (products) asumimos snapshot aplicado.
    if "products" in inspector.get_table_names():
        # Idempotente: no recrear
        return

    # Crear todas las tablas conocidas por el metadata actual.
    # Esto asume que Base.metadata está limpio de tablas deprecated.
    Base.metadata.create_all(bind)


def downgrade() -> None:  # pragma: no cover
    # No se soporta downgrade de snapshot consolidado para evitar pérdida de datos.
    pass
