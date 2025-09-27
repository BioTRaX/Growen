"""stock ledger + sales related indexes + unique document_number

Revision ID: 20250926_stock_ledger_dup_deprecated
Revises: 20250914_extend_supplier_files
Create Date: 2025-09-26
"""
# NG-HEADER: Nombre de archivo: 20250926_stock_ledger_and_sales_indexes.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_stock_ledger_and_sales_indexes.py
# NG-HEADER: Descripción: Crea tabla stock_ledger, índices ventas/devoluciones y unique document_number.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from alembic import op
import sqlalchemy as sa

revision = '20250926_stock_ledger_dup_deprecated'
down_revision = '20250914_extend_supplier_files'
branch_labels = None
depends_on = None


def upgrade() -> None:  # deprecated noop
    pass


def downgrade() -> None:  # deprecated noop
    pass
