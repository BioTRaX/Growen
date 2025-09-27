# NG-HEADER: Nombre de archivo: 20250926_stock_ledger.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_stock_ledger.py
# NG-HEADER: Descripción: Crea tabla stock_ledger para movimientos de inventario.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Crear tabla stock_ledger

Revision ID: 20250926_stock_ledger_deprecated
Revises: 20250926_sales_status_customer_date_idx
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250926_stock_ledger_deprecated'
down_revision = '20250926_sales_status_customer_date_idx'
branch_labels = None
depends_on = None

def upgrade() -> None:  # deprecated noop
    pass


def downgrade() -> None:  # deprecated noop
    pass
    op.drop_table('stock_ledger')
