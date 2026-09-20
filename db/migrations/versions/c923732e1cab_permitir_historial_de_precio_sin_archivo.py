#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: c923732e1cab_permitir_historial_de_precio_sin_archivo.py
# NG-HEADER: Ubicación: db/migrations/versions/c923732e1cab_permitir_historial_de_precio_sin_archivo.py
# NG-HEADER: Descripción: Permite registrar precios de compras sin archivo de proveedor asociado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Permitir historial de precio sin archivo.

Revision ID: c923732e1cab
Revises: 20260716_purchase_ingestion_v2
Create Date: 2026-07-17 19:09:11.656810
"""

from alembic import op
import sqlalchemy as sa


revision = "c923732e1cab"
down_revision = "20260716_purchase_ingestion_v2"
branch_labels = None
depends_on = None


def _file_fk_nullable() -> bool:
    columns = sa.inspect(op.get_bind()).get_columns("supplier_price_history")
    return next(column for column in columns if column["name"] == "file_fk")["nullable"]


def upgrade() -> None:
    if not _file_fk_nullable():
        op.alter_column(
            "supplier_price_history",
            "file_fk",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    if not _file_fk_nullable():
        return
    null_rows = op.get_bind().execute(
        sa.text("SELECT count(*) FROM supplier_price_history WHERE file_fk IS NULL")
    ).scalar_one()
    if null_rows:
        raise RuntimeError(
            "No se puede restaurar file_fk NOT NULL: existen historiales sin archivo asociado"
        )
    op.alter_column(
        "supplier_price_history",
        "file_fk",
        existing_type=sa.Integer(),
        nullable=False,
    )
