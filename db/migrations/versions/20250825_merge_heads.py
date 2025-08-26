"""merge heads: supplier_price_history_idx + add_identifier_to_users

Revision ID: 20250825_merge_heads
Revises: 20250114_supplier_price_history_idx, 20250825_add_identifier_to_users
Create Date: 2025-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250825_merge_heads"
# Merge both branches: the import summary column branch and the users identifier branch
down_revision = ("20250120_add_summary_json_to_import_jobs", "20250825_add_identifier_to_users")
branch_labels = None
depends_on = None


def upgrade():
    # No-op merge; schema already defined by parent heads.
    pass


def downgrade():
    # Split is ambiguous; generally leave as no-op.
    pass
