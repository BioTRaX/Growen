# NG-HEADER: Nombre de archivo: 20250825_fix_identifier_users_force.py
# NG-HEADER: Ubicación: db/migrations/versions/20250825_fix_identifier_users_force.py
# NG-HEADER: Descripción: Migración Alembic: corrige identificadores forzados en usuarios.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""force add identifier to users if still missing

This migration is a safety net in case previous revisions didn't add the
`users.identifier` column due to environment inconsistencies. It is idempotent.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20250825_fix_identifier_users_force"
down_revision = "20250825_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1) Add column if missing
    bind.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users'
              AND column_name = 'identifier'
              AND table_schema = current_schema()
          ) THEN
            ALTER TABLE users ADD COLUMN identifier VARCHAR(64);
          END IF;
        END $$;
        """
    ))

    # 2) Backfill identifier from email prefix or fallback
    bind.execute(text(
        """
        UPDATE users
           SET identifier = COALESCE(identifier, NULLIF(split_part(email, '@', 1), ''), 'user_' || id::text)
         WHERE identifier IS NULL;
        """
    ))

    # 3) Create unique constraint if missing
    bind.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_identifier'
          ) THEN
            BEGIN
              ALTER TABLE users ADD CONSTRAINT uq_users_identifier UNIQUE (identifier);
            EXCEPTION WHEN duplicate_object THEN
              -- ignore if an equivalent unique index/constraint already exists under a different name
            END;
          END IF;
        END $$;
        """
    ))

    # 4) Enforce NOT NULL once populated
    try:
        op.alter_column("users", "identifier", nullable=False)
    except Exception:
        # If some rows are still NULL for any reason, keep it nullable to avoid breaking
        pass


def downgrade():
    # Do not drop the column to avoid data loss; this is a safety migration
    pass
