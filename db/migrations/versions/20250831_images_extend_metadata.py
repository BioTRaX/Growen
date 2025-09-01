"""extend images with metadata and path

Revision ID: 20250831_images_extend_metadata
Revises: 20250831_purchases_module
Create Date: 2025-08-31 20:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_images_extend_metadata"
down_revision = "20250831_purchases_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("path", sa.String(length=600), nullable=True))
    op.add_column("images", sa.Column("alt_text", sa.String(length=300), nullable=True))
    op.add_column("images", sa.Column("title_text", sa.String(length=300), nullable=True))
    op.add_column("images", sa.Column("mime", sa.String(length=100), nullable=True))
    op.add_column("images", sa.Column("bytes", sa.Integer(), nullable=True))
    op.add_column("images", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("images", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("images", sa.Column("checksum_sha256", sa.String(length=64), nullable=True))
    op.add_column("images", sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.add_column("images", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))


def downgrade() -> None:
    op.drop_column("images", "updated_at")
    op.drop_column("images", "created_at")
    op.drop_column("images", "checksum_sha256")
    op.drop_column("images", "height")
    op.drop_column("images", "width")
    op.drop_column("images", "bytes")
    op.drop_column("images", "mime")
    op.drop_column("images", "title_text")
    op.drop_column("images", "alt_text")
    op.drop_column("images", "path")
