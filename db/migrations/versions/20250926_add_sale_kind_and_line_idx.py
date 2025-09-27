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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    sales_cols = {c['name'] for c in inspector.get_columns('sales')} if 'sales' in inspector.get_table_names() else set()
    sale_lines_exists = 'sale_lines' in inspector.get_table_names()

    # Columna sale_kind sólo si falta
    if 'sale_kind' not in sales_cols and 'sales' in inspector.get_table_names():
        with op.batch_alter_table("sales") as batch:
            batch.add_column(sa.Column("sale_kind", sa.String(16), server_default="MOSTRADOR", nullable=False))
    # Constraint (best-effort) si la tabla existe
    if 'sales' in inspector.get_table_names():
        try:
            op.create_check_constraint("ck_sales_kind", "sales", "sale_kind IN ('MOSTRADOR','PEDIDO')")
        except Exception:
            pass

    def index_exists(table: str, name: str) -> bool:
        try:
            return any(ix.get('name') == name for ix in inspector.get_indexes(table))
        except Exception:
            return False

    if sale_lines_exists:
        if not index_exists('sale_lines', 'ix_sale_lines_product_id'):
            try:
                op.create_index("ix_sale_lines_product_id", "sale_lines", ["product_id"], unique=False)
            except Exception:
                pass
        if not index_exists('sale_lines', 'ix_sale_lines_product_sale'):
            try:
                op.create_index("ix_sale_lines_product_sale", "sale_lines", ["product_id","sale_id"], unique=False)
            except Exception:
                pass


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