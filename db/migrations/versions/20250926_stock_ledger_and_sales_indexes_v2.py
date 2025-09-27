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
    """Idempotente: crea tabla e índices solo si faltan.

    Esta migración fue ajustada porque en entornos con múltiples revisiones duplicadas
    (stock_ledger original/deprecated) la tabla pudo haberse creado previamente.
    Para evitar errores DuplicateTable / DuplicateIndex se inspecciona antes.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    def table_has_index(table: str, index_name: str) -> bool:
        try:
            idxs = inspector.get_indexes(table)
        except Exception:
            return False
        return any(ix.get('name') == index_name for ix in idxs)

    # Tabla principal stock_ledger
    if 'stock_ledger' not in existing_tables:
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
    # Índices de stock_ledger
    if not table_has_index('stock_ledger', 'ix_stock_ledger_product_created'):
        try:
            op.create_index('ix_stock_ledger_product_created', 'stock_ledger', ['product_id', 'created_at'])
        except Exception:
            pass
    if not table_has_index('stock_ledger', 'ix_stock_ledger_source'):
        try:
            op.create_index('ix_stock_ledger_source', 'stock_ledger', ['source_type', 'source_id'])
        except Exception:
            pass

    # Helper para crear índice si falta
    def ensure_index(table: str, name: str, columns: list[str]):
        if table not in existing_tables:
            return
        if table_has_index(table, name):
            return
        try:
            op.create_index(name, table, columns)
        except Exception:
            # Ignorar condiciones de carrera o ya creado
            pass

    # Índices en tablas de ventas / devoluciones / líneas
    ensure_index('sales', 'ix_sales_sale_date', ['sale_date'])
    ensure_index('sales', 'ix_sales_customer_id', ['customer_id'])
    ensure_index('sale_lines', 'ix_sale_lines_product_id', ['product_id'])
    ensure_index('returns', 'ix_returns_created_at', ['created_at'])
    ensure_index('return_lines', 'ix_return_lines_product_id', ['product_id'])

    # Unique parcial en customers.document_number (Postgres) o índice simple fallback
    dialect = bind.dialect.name
    if 'customers' in existing_tables:
        if dialect == 'postgresql':
            op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_document_number ON customers(document_number) WHERE document_number IS NOT NULL")
        else:
            # Para SQLite/MySQL se intenta crear índice normal si no existe
            if not table_has_index('customers', 'ix_customers_document_number'):
                try:
                    op.create_index('ix_customers_document_number', 'customers', ['document_number'])
                except Exception:
                    pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    dialect = bind.dialect.name

    def safe_drop_index(name: str, table: str):
        if table not in existing_tables:
            return
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass

    # customers
    if 'customers' in existing_tables:
        if dialect == 'postgresql':
            try:
                op.execute("DROP INDEX IF EXISTS ux_customers_document_number")
            except Exception:
                pass
        else:
            safe_drop_index('ix_customers_document_number', 'customers')

    for idx, table in [
        ('ix_return_lines_product_id', 'return_lines'),
        ('ix_returns_created_at', 'returns'),
        ('ix_sale_lines_product_id', 'sale_lines'),
        ('ix_sales_customer_id', 'sales'),
        ('ix_sales_sale_date', 'sales'),
    ]:
        safe_drop_index(idx, table)

    # stock_ledger indices y tabla
    if 'stock_ledger' in existing_tables:
        safe_drop_index('ix_stock_ledger_source', 'stock_ledger')
        safe_drop_index('ix_stock_ledger_product_created', 'stock_ledger')
        try:
            op.drop_table('stock_ledger')
        except Exception:
            pass
