# NG-HEADER: Nombre de archivo: 20250926_add_purchase_line_meta.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_add_purchase_line_meta.py
# NG-HEADER: Descripción: Agrega columna meta (JSON) a purchase_lines para trazabilidad de enriquecimiento
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add purchase_lines.meta JSON column

Revision ID: 20250926_add_purchase_line_meta
Revises: 20250926_merge_sales_indexes_and_stock_ledger
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# Revisiones Alembic
revision = '20250926_add_purchase_line_meta'
down_revision = '20250926_merge_sales_indexes_and_stock_ledger'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('purchase_lines', sa.Column('meta', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('purchase_lines', 'meta')
