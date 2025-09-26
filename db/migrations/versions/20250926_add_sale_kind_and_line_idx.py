#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250926_add_sale_kind_and_line_idx.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_add_sale_kind_and_line_idx.py
# NG-HEADER: Descripción: Agrega columna sale_kind (MOSTRADOR|PEDIDO) e índice product_id en sale_lines
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add sale_kind and sale_lines product idx

Revision ID: 20250926_add_sale_kind_and_line_idx
Revises: 20250926_returns_module
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250926_add_sale_kind_and_line_idx"
down_revision = "20250926_returns_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales") as batch:
        batch.add_column(sa.Column("sale_kind", sa.String(16), server_default="MOSTRADOR", nullable=False))
    # Añadir constraint opcional (soft) validando valores
    try:
        op.create_check_constraint("ck_sales_kind", "sales", "sale_kind IN ('MOSTRADOR','PEDIDO')")
    except Exception:
        pass
    op.create_index("ix_sale_lines_product_id", "sale_lines", ["product_id"], unique=False)
    # Índice compuesto para consultas por producto y agrupación por venta
    op.create_index("ix_sale_lines_product_sale", "sale_lines", ["product_id","sale_id"], unique=False)


def downgrade() -> None:
    try:
        op.drop_index("ix_sale_lines_product_sale", table_name="sale_lines")
    except Exception:
        pass
    try:
        op.drop_index("ix_sale_lines_product_id", table_name="sale_lines")
    except Exception:
        pass
    try:
        op.drop_constraint("ck_sales_kind", "sales", type_="check")
    except Exception:
        pass
    with op.batch_alter_table("sales") as batch:
        try:
            batch.drop_column("sale_kind")
        except Exception:
            pass