# NG-HEADER: Nombre de archivo: 20250901_import_logs.py
# NG-HEADER: Ubicación: db/migrations/versions/20250901_import_logs.py
# NG-HEADER: Descripción: Migración Alembic: crea registros para import logs.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""import logs table

Revision ID: 20250901_import_logs
Revises: 20250831_purchases_module
Create Date: 2025-09-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250901_import_logs"
down_revision = "20250831_purchases_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default="INFO"),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("import_logs")
