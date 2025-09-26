# NG-HEADER: Nombre de archivo: 20250113_import_job_rows_status_idx.py
# NG-HEADER: Ubicación: db/migrations/versions/20250113_import_job_rows_status_idx.py
# NG-HEADER: Descripción: Migración Alembic: crea índice por estado en import_job_rows.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa

revision = "20250113_import_job_rows_status_idx"
down_revision = "20241105_auth_roles_sessions"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _idx_exists(table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in _insp().get_indexes(table))


def upgrade() -> None:
    if not _idx_exists("import_job_rows", "ix_import_job_rows_job_status"):
        op.create_index(
            "ix_import_job_rows_job_status",
            "import_job_rows",
            ["job_id", "status"],
        )


def downgrade() -> None:
    if _idx_exists("import_job_rows", "ix_import_job_rows_job_status"):
        op.drop_index("ix_import_job_rows_job_status", table_name="import_job_rows")
