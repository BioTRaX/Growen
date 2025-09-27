# NG-HEADER: Nombre de archivo: 20250926_merge_sales_indexes_and_stock_ledger.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_merge_sales_indexes_and_stock_ledger.py
# NG-HEADER: Descripción: Merge final unifica heads previos de sales indexes y stock ledger antes de cascade fk
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge sales indexes and stock ledger heads

Revision ID: 20250926_merge_sales_indexes_and_stock_ledger
Revises: 20250926_add_purchase_line_meta, 20250926_sales_status_customer_date_idx
Create Date: 2025-09-26
"""
from __future__ import annotations

revision = '20250926_merge_sales_indexes_and_stock_ledger'
down_revision = ('20250926_add_purchase_line_meta','20250926_sales_status_customer_date_idx')
branch_labels = None
depends_on = None

def upgrade():  # pragma: no cover
    pass

def downgrade():  # pragma: no cover
    pass
