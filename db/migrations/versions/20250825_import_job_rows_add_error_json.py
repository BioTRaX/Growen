# NG-HEADER: Nombre de archivo: 20250825_import_job_rows_add_error_json.py
# NG-HEADER: Ubicación: db/migrations/versions/20250825_import_job_rows_add_error_json.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add missing columns to import_job_rows and ensure import_jobs.summary_json

This migration is idempotent: it only adds columns if they don't exist.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250825_import_job_rows_add_error_json"
down_revision = "20250825_fix_identifier_users_force"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _insp().has_table(name)


def _col_exists(table: str, col: str) -> bool:
    return any(c["name"] == col for c in _insp().get_columns(table))


def upgrade() -> None:
    # Ensure import_jobs.summary_json exists
    if _table_exists("import_jobs") and not _col_exists("import_jobs", "summary_json"):
        op.add_column("import_jobs", sa.Column("summary_json", sa.JSON(), nullable=True))

    # Ensure import_job_rows has the expected columns used by current code
    if _table_exists("import_job_rows"):
        if not _col_exists("import_job_rows", "error"):
            op.add_column("import_job_rows", sa.Column("error", sa.String(length=200), nullable=True))
        if not _col_exists("import_job_rows", "row_json_normalized"):
            op.add_column("import_job_rows", sa.Column("row_json_normalized", sa.JSON(), nullable=True))


def downgrade() -> None:
    # Be conservative: only drop columns if present
    if _table_exists("import_job_rows"):
        if _col_exists("import_job_rows", "row_json_normalized"):
            op.drop_column("import_job_rows", "row_json_normalized")
        if _col_exists("import_job_rows", "error"):
            op.drop_column("import_job_rows", "error")
    if _table_exists("import_jobs") and _col_exists("import_jobs", "summary_json"):
        op.drop_column("import_jobs", "summary_json")
