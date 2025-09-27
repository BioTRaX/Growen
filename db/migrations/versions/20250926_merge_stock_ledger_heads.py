# NG-HEADER: Nombre de archivo: 20250926_merge_stock_ledger_heads.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_merge_stock_ledger_heads.py
# NG-HEADER: Descripción: Merge de múltiples heads (stock ledger y meta purchase line) en una sola línea
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge heads for stock ledger and purchase line meta

Revision ID: 20250926_merge_stock_ledger_heads
Revises: 20250926_add_purchase_line_meta, 20250926_stock_ledger_v2
Create Date: 2025-09-26
"""
from __future__ import annotations

# Esta migración no altera el esquema: sólo consolida heads.
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = '20250926_merge_stock_ledger_heads'
down_revision = ('20250926_add_purchase_line_meta', '20250926_stock_ledger_v2')
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover
    pass


def downgrade() -> None:  # pragma: no cover
    pass
