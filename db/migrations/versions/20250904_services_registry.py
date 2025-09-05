"""services registry tables

Revision ID: 20250904_services_registry
Revises: 20250901_merge_images_and_import_logs
Create Date: 2025-09-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250904_services_registry"
down_revision = "20250901_merge_images_and_import_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="stopped"),
        sa.Column("auto_start", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("uptime_s", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("name", name="ux_services_name"),
    )
    op.create_check_constraint(
        "ck_services_status",
        "services",
        "status IN ('stopped','starting','running','degraded','failed')",
    )

    op.create_table(
        "service_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("host", sa.String(128), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("level", sa.String(16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("hint", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint(
        "ck_service_logs_action",
        "service_logs",
        "action IN ('start','stop','status','health','panic')",
    )

    op.create_table(
        "startup_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ttfb_ms", sa.Integer(), nullable=True),
        sa.Column("app_ready_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("meta", sa.JSON(), nullable=True),
    )

    # Seed default services (best-effort; skip on error)
    try:
        conn = op.get_bind()
        services = [
            ("pdf_import", False),
            ("playwright", False),
            ("image_processing", False),
            ("dramatiq", False),
            ("scheduler", False),
            ("tiendanube", False),
            ("notifier", False),
        ]
        for name, auto in services:
            conn.execute(
                sa.text("INSERT INTO services (name, status, auto_start) VALUES (:n, 'stopped', :a)"),
                {"n": name, "a": bool(auto)},
            )
    except Exception:
        # ignore in case of permission issues or idempotent re-run
        pass


def downgrade() -> None:
    op.drop_table("startup_metrics")
    op.drop_constraint("ck_service_logs_action", "service_logs", type_="check")
    op.drop_table("service_logs")
    op.drop_constraint("ck_services_status", "services", type_="check")
    op.drop_table("services")
