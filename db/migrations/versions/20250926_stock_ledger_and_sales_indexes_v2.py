# NG-HEADER: Nombre de archivo: 20250926_stock_ledger_and_sales_indexes_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_stock_ledger_and_sales_indexes_v2.py
# NG-HEADER: Descripción: Crea tabla stock_ledger + índices ventas/devoluciones (versión corregida id único)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""stock ledger + sales related indexes + unique document_number (v2)

Revision ID: 20250926_stock_ledger_v2
Revises: 20250914_extend_supplier_files
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20250926_stock_ledger_v2'
down_revision = '20250914_extend_supplier_files'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear tabla stock_ledger si no existe
    op.create_table(
        'stock_ledger',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    op.create_index('ix_stock_ledger_product_created', 'stock_ledger', ['product_id', 'created_at'])
    op.create_index('ix_stock_ledger_source', 'stock_ledger', ['source_type', 'source_id'])

    # Índices en tablas de ventas / devoluciones / líneas
    op.create_index('ix_sales_sale_date', 'sales', ['sale_date'])
    op.create_index('ix_sales_customer_id', 'sales', ['customer_id'])
    op.create_index('ix_sale_lines_product_id', 'sale_lines', ['product_id'])
    op.create_index('ix_returns_created_at', 'returns', ['created_at'])
    op.create_index('ix_return_lines_product_id', 'return_lines', ['product_id'])

    # Unique parcial en customers.document_number (Postgres) o índice simple fallback
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_document_number ON customers(document_number) WHERE document_number IS NOT NULL")
    else:
        op.create_index('ix_customers_document_number', 'customers', ['document_number'])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ux_customers_document_number")
    else:
        op.drop_index('ix_customers_document_number', table_name='customers')

    for idx, table in [
        ('ix_return_lines_product_id', 'return_lines'),
        ('ix_returns_created_at', 'returns'),
        ('ix_sale_lines_product_id', 'sale_lines'),
        ('ix_sales_customer_id', 'sales'),
        ('ix_sales_sale_date', 'sales'),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass

    op.drop_index('ix_stock_ledger_source', table_name='stock_ledger')
    op.drop_index('ix_stock_ledger_product_created', table_name='stock_ledger')
    op.drop_table('stock_ledger')
