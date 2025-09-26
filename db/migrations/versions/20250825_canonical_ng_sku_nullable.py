# NG-HEADER: Nombre de archivo: 20250825_canonical_ng_sku_nullable.py
# NG-HEADER: Ubicación: db/migrations/versions/20250825_canonical_ng_sku_nullable.py
# NG-HEADER: Descripción: Migración Alembic: hace opcional el SKU canónico en suppliers.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""make canonical_products.ng_sku nullable to allow post-insert generation

Revision ID: 20250825_canonical_ng_sku_nullable
Revises: 20250825_merge_heads
Create Date: 2025-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250825_canonical_ng_sku_nullable"
down_revision = "20250825_import_job_rows_add_error_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # In Postgres it's safe to alter nullability directly
    try:
        op.alter_column(
            "canonical_products",
            "ng_sku",
            existing_type=sa.String(length=20),
            nullable=True,
        )
    except Exception:
        # Be lenient if already nullable or column missing in some envs
        pass


def downgrade() -> None:
    try:
        op.alter_column(
            "canonical_products",
            "ng_sku",
            existing_type=sa.String(length=20),
            nullable=False,
        )
    except Exception:
        pass
