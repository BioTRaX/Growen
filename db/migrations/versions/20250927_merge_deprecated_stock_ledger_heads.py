#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250927_merge_deprecated_stock_ledger_heads.py
# NG-HEADER: Ubicación: db/migrations/versions/20250927_merge_deprecated_stock_ledger_heads.py
# NG-HEADER: Descripción: Merge de heads duplicados stock_ledger y sku_sequences a una sola línea
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge deprecated stock ledger heads with sku sequences

Revision ID: 20250927_merge_deprecated_stock_ledger_heads
Revises: 20250926_stock_ledger_deprecated, 20250926_stock_ledger_dup_deprecated, 20250927_add_sku_sequences
Create Date: 2025-09-27
"""
from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = '20250927_merge_deprecated_stock_ledger_heads'
down_revision = (
    '20250926_stock_ledger_deprecated',
    '20250926_stock_ledger_dup_deprecated',
    '20250927_add_sku_sequences',
)
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover
    pass


def downgrade() -> None:  # pragma: no cover
    pass
