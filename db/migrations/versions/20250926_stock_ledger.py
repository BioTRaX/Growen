# NG-HEADER: Nombre de archivo: 20250926_stock_ledger.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_stock_ledger.py
# NG-HEADER: Descripción: Crea tabla stock_ledger para movimientos de inventario.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Crear tabla stock_ledger

Revision ID: 20250926_stock_ledger
Revises: 20250926_sales_status_customer_date_idx
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250926_stock_ledger'
down_revision = '20250926_sales_status_customer_date_idx'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'stock_ledger',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),  # sale|return|adjust|purchase (futuro)
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),  # negativo reduce stock, positivo incrementa
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    op.create_index('ix_stock_ledger_product_created', 'stock_ledger', ['product_id', 'created_at'])
    op.create_index('ix_stock_ledger_source', 'stock_ledger', ['source_type', 'source_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_stock_ledger_source', table_name='stock_ledger')
    op.drop_index('ix_stock_ledger_product_created', table_name='stock_ledger')
    op.drop_table('stock_ledger')
