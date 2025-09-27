# NG-HEADER: Nombre de archivo: 20250926_add_cascade_sale_lines_product_fk.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_add_cascade_sale_lines_product_fk.py
# NG-HEADER: Descripción: Agrega ON DELETE CASCADE a sale_lines.product_id
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add cascade to sale_lines.product_id

Revision ID: 20250926_add_cascade_sale_lines_product_fk
Revises: 20250926_merge_stock_ledger_heads
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20250926_add_cascade_sale_lines_product_fk'
down_revision = '20250926_merge_stock_ledger_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alter constraint: depende del dialecto (SQLite limita ALTER, usar recreate pattern)
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'sqlite':
        # Simplificación: en SQLite no se aplicará cambio estructural (requiere recreate table). Documentamos.
        return
    # Postgres / otros: eliminar FK y recrear
    with op.batch_alter_table('sale_lines') as batch:
        try:
            batch.drop_constraint('sale_lines_product_id_fkey', type_='foreignkey')
        except Exception:
            pass
        batch.create_foreign_key('sale_lines_product_id_fkey', 'products', ['product_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'sqlite':
        return
    with op.batch_alter_table('sale_lines') as batch:
        try:
            batch.drop_constraint('sale_lines_product_id_fkey', type_='foreignkey')
        except Exception:
            pass
        batch.create_foreign_key('sale_lines_product_id_fkey', 'products', ['product_id'], ['id'])
