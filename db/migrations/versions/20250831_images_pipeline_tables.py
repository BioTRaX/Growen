# NG-HEADER: Nombre de archivo: 20250831_images_pipeline_tables.py
# NG-HEADER: Ubicación: db/migrations/versions/20250831_images_pipeline_tables.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""images pipeline tables and flags

Revision ID: 20250831_images_pipeline_tables
Revises: 20250831_images_extend_metadata
Create Date: 2025-08-31 21:15:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_images_pipeline_tables"
down_revision = "20250831_images_extend_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend images with flags
    op.add_column("images", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("images", sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("images", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))

    # image_versions
    op.create_table(
        "image_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("image_id", sa.Integer(), sa.ForeignKey("images.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("path", sa.String(length=700), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=True),
        sa.Column("mime", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=800), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint(
        "ck_image_versions_kind",
        "image_versions",
        "kind IN ('original','bg_removed','watermarked','thumb','card','full')",
    )
    op.create_index("ix_image_versions_image_kind", "image_versions", ["image_id", "kind"])

    # image_reviews
    op.create_table(
        "image_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("image_id", sa.Integer(), sa.ForeignKey("images.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint(
        "ck_image_reviews_status", "image_reviews", "status IN ('pending','approved','rejected')"
    )
    op.create_index("ix_image_reviews_status", "image_reviews", ["status"])

    # image_jobs
    op.create_table(
        "image_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="off"),
        sa.Column("window_start", sa.Time(), nullable=True),
        sa.Column("window_end", sa.Time(), nullable=True),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("rate_rps", sa.Float(), nullable=True, server_default="1"),
        sa.Column("burst", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("log_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("purge_ttl_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint(
        "ck_image_jobs_mode", "image_jobs", "mode IN ('off','on','window')"
    )
    op.create_index("ux_image_jobs_name", "image_jobs", ["name"], unique=True)

    # image_job_logs
    op.create_table(
        "image_job_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_image_job_logs_job_created", "image_job_logs", ["job_name", "created_at"]) 

    # external_media_map
    op.create_table(
        "external_media_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("remote_media_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_external_media_map_provider_product", "external_media_map", ["provider", "product_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_external_media_map_provider_product", table_name="external_media_map")
    op.drop_table("external_media_map")

    op.drop_index("ix_image_job_logs_job_created", table_name="image_job_logs")
    op.drop_table("image_job_logs")

    op.drop_index("ux_image_jobs_name", table_name="image_jobs")
    op.drop_table("image_jobs")

    op.drop_index("ix_image_reviews_status", table_name="image_reviews")
    op.drop_table("image_reviews")

    op.drop_index("ix_image_versions_image_kind", table_name="image_versions")
    op.drop_table("image_versions")

    op.drop_column("images", "active")
    op.drop_column("images", "locked")
    op.drop_column("images", "is_primary")

