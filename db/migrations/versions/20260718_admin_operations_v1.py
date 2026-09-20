#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260718_admin_operations_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260718_admin_operations_v1.py
# NG-HEADER: Descripción: Persiste operaciones administrativas, feedback de chat y gobierno de prompts.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Persistencia para la evolución del panel administrativo.

Revision ID: 20260718_admin_operations_v1
Revises: 20260717_sales_customers_v4
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260718_admin_operations_v1"
down_revision = "20260717_sales_customers_v4"
branch_labels = None
depends_on = None


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(table) and column.name not in _columns(inspector, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("chat_sessions"):
        _add_column_if_missing("chat_sessions", sa.Column("channel", sa.String(24), nullable=False, server_default="web"))
        _add_column_if_missing("chat_sessions", sa.Column("assigned_user_id", sa.Integer(), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("detected_intent", sa.String(64), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("sentiment", sa.String(24), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("classification_confidence", sa.Numeric(5, 4), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("classification_model", sa.String(120), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("problem_signals", sa.JSON(), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("classified_at", sa.DateTime(), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        _add_column_if_missing("chat_sessions", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        inspector = sa.inspect(bind)
        foreign_names = {fk.get("name") for fk in inspector.get_foreign_keys("chat_sessions")}
        if "fk_chat_sessions_assigned_user" not in foreign_names:
            op.create_foreign_key(
                "fk_chat_sessions_assigned_user", "chat_sessions", "users", ["assigned_user_id"], ["id"], ondelete="SET NULL"
            )
        if "fk_chat_sessions_reviewed_by" not in foreign_names:
            op.create_foreign_key(
                "fk_chat_sessions_reviewed_by", "chat_sessions", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL"
            )

    inspector = sa.inspect(bind)
    if not inspector.has_table("drive_sync_runs"):
        op.create_table(
            "drive_sync_runs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("parent_run_id", sa.String(64), sa.ForeignKey("drive_sync_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_folder_id", sa.String(256), nullable=True),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("initiated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_filename", sa.String(500), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('queued','running','cancel_requested','cancelled','completed','partial','failed')",
                name="ck_drive_sync_runs_status",
            ),
        )
        op.create_index("ix_drive_sync_runs_status_created", "drive_sync_runs", ["status", "created_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("drive_sync_items"):
        op.create_table(
            "drive_sync_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.String(64), sa.ForeignKey("drive_sync_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("source_file_id", sa.String(256), nullable=True),
            sa.Column("filename", sa.String(500), nullable=False),
            sa.Column("sku", sa.String(120), nullable=True),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('pending','processing','processed','failed','skipped','cancelled')",
                name="ck_drive_sync_items_status",
            ),
            sa.UniqueConstraint("run_id", "position", name="uq_drive_sync_items_run_position"),
        )
        op.create_index("ix_drive_sync_items_run_status", "drive_sync_items", ["run_id", "status"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("scheduler_settings"):
        op.create_table(
            "scheduler_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Argentina/Buenos_Aires"),
            sa.Column("start_hour", sa.String(5), nullable=False, server_default="02:00"),
            sa.Column("interval_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("update_frequency_days", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("max_products_per_run", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("prioritize_mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("scheduler_runs"):
        op.create_table(
            "scheduler_runs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("trigger", sa.String(16), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("initiated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("products_enqueued", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sources_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Numeric(12, 3), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("config_snapshot", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_scheduler_runs_status_created", "scheduler_runs", ["status", "created_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_index_tasks"):
        op.create_table(
            "knowledge_index_tasks",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("task_type", sa.String(24), nullable=False),
            sa.Column("target", sa.String(500), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_knowledge_index_tasks_status_created", "knowledge_index_tasks", ["status", "created_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("catalog_generation_runs"):
        op.create_table(
            "catalog_generation_runs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("product_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("artifact_filename", sa.String(500), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_catalog_generation_runs_status_created", "catalog_generation_runs", ["status", "created_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("catalog_generation_events"):
        op.create_table(
            "catalog_generation_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.String(64), sa.ForeignKey("catalog_generation_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("step", sa.String(64), nullable=False),
            sa.Column("level", sa.String(16), nullable=False, server_default="INFO"),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("run_id", "sequence", name="uq_catalog_generation_event_sequence"),
        )
        op.create_index("ix_catalog_generation_events_run", "catalog_generation_events", ["run_id", "sequence"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("chat_message_feedback"):
        op.create_table(
            "chat_message_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rating", sa.String(16), nullable=False),
            sa.Column("categories", sa.JSON(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("message_id", "reviewer_user_id", name="uq_chat_feedback_message_reviewer"),
        )
        op.create_index("ix_chat_message_feedback_rating_created", "chat_message_feedback", ["rating", "created_at"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_prompt_versions"):
        op.create_table(
            "ai_prompt_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prompt_key", sa.String(100), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="candidate"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("metrics", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_key_version"),
        )
        op.create_index("ix_ai_prompt_versions_key_status", "ai_prompt_versions", ["prompt_key", "status"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_prompt_evaluations"):
        op.create_table(
            "ai_prompt_evaluations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prompt_version_id", sa.Integer(), sa.ForeignKey("ai_prompt_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dataset_version", sa.String(64), nullable=False),
            sa.Column("sample_count", sa.Integer(), nullable=False),
            sa.Column("composite_score", sa.Numeric(7, 4), nullable=False),
            sa.Column("safety_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_ai_prompt_evaluations_prompt_created", "ai_prompt_evaluations", ["prompt_version_id", "created_at"])


def downgrade() -> None:
    raise RuntimeError(
        "El downgrade de 20260718_admin_operations_v1 se rechaza porque eliminaría historial operativo, feedback y versiones de prompts."
    )
