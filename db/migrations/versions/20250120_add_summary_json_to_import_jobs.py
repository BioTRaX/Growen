# NG-HEADER: Nombre de archivo: 20250120_add_summary_json_to_import_jobs.py
# NG-HEADER: Ubicación: db/migrations/versions/20250120_add_summary_json_to_import_jobs.py
# NG-HEADER: Descripción: Migración Alembic: agrega summary_json a import_jobs.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add summary_json column to import_jobs (idempotent)

Revision ID: 20250120_add_summary_json_to_import_jobs
Revises: 20250114_supplier_price_history_idx
Create Date: 2025-01-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20250120_add_summary_json_to_import_jobs"
down_revision = "20250114_supplier_price_history_idx"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Add summary_json JSON column if missing
    bind.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'import_jobs'
              AND column_name = 'summary_json'
              AND table_schema = current_schema()
          ) THEN
            ALTER TABLE import_jobs ADD COLUMN summary_json JSON;
          END IF;
        END $$;
        """
    ))


def downgrade():
    # Safe no-op: keep column; if you really need to drop it, uncomment below.
    # op.drop_column('import_jobs', 'summary_json')
    pass
