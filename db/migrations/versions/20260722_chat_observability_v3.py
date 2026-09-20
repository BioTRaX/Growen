#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260722_chat_observability_v3.py
# NG-HEADER: Ubicación: db/migrations/versions/20260722_chat_observability_v3.py
# NG-HEADER: Descripción: Métricas seguras de ejecuciones y tools de chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Métricas seguras de ejecuciones y tools de chat."""

from alembic import op
import sqlalchemy as sa

revision = "20260722_chat_observability_v3"
down_revision = "20260722_chat_rag_policy_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("chat_sessions.session_id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False, unique=True),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("account_role", sa.String(20), nullable=False),
        sa.Column("effective_role", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(14, 6), nullable=True),
        sa.Column("rag_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_runs_created_channel_status", "chat_runs", ["created_at", "channel", "status"])
    op.create_index("ix_chat_runs_role_model", "chat_runs", ["effective_role", "model"])
    op.create_table(
        "chat_tool_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("chat_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_tool_events_tool_created", "chat_tool_events", ["tool_name", "created_at"])
    op.create_table(
        "chat_feedback_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False, server_default="web"),
        sa.Column("account_role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating IN ('positive','negative')", name="ck_chat_feedback_events_rating"),
    )
    op.create_index("ix_chat_feedback_events_rating_created", "chat_feedback_events", ["rating", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM chat_runs LIMIT 1")).first() or bind.execute(sa.text("SELECT 1 FROM chat_feedback_events LIMIT 1")).first():
        raise RuntimeError("Downgrade bloqueado: existe trazabilidad de chat")
    op.drop_table("chat_feedback_events")
    op.drop_table("chat_tool_events")
    op.drop_table("chat_runs")
