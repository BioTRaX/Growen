#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260816_chat_rollout_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260816_chat_rollout_v1.py
# NG-HEADER: Descripción: Estado y trazabilidad segura del rollout gradual de Chat.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260816_chat_rollout_v1"
down_revision = "20260726_canonical_knowledge_v1"
branch_labels = None
depends_on = None


def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "chat_rollout_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phase", sa.String(32), nullable=False, server_default="disabled"),
        sa.Column("status", sa.String(16), nullable=False, server_default="paused"),
        sa.Column("auto_advance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("phase_started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_chat_rollout_state_singleton"),
        sa.CheckConstraint("status IN ('active','paused')", name="ck_chat_rollout_state_status"),
    )
    op.create_table(
        "chat_rollout_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_phase", sa.String(32), nullable=False),
        sa.Column("to_phase", sa.String(32), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("metrics", _json_type(bind), nullable=False, server_default="{}"),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_rollout_events_created_phase", "chat_rollout_events", ["created_at", "to_phase"])
    op.create_table(
        "chat_rollout_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("check_name", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_rollout_checks_phase_created", "chat_rollout_checks", ["phase", "created_at"])
    op.bulk_insert(
        sa.table(
            "chat_rollout_state",
            sa.column("id", sa.Integer()),
            sa.column("phase", sa.String()),
            sa.column("status", sa.String()),
            sa.column("auto_advance", sa.Boolean()),
            sa.column("version", sa.Integer()),
            sa.column("reason_code", sa.String()),
        ),
        [{"id": 1, "phase": "disabled", "status": "paused", "auto_advance": False, "version": 1, "reason_code": "initial_safe_state"}],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("chat_rollout_events", "chat_rollout_checks"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Downgrade bloqueado: existe trazabilidad de rollout")
    state = bind.execute(sa.text("SELECT phase, status FROM chat_rollout_state WHERE id = 1")).first()
    if state and (state.phase != "disabled" or state.status != "paused"):
        raise RuntimeError("Downgrade bloqueado: el rollout abandonó el estado inicial")
    op.drop_index("ix_chat_rollout_checks_phase_created", table_name="chat_rollout_checks")
    op.drop_table("chat_rollout_checks")
    op.drop_index("ix_chat_rollout_events_created_phase", table_name="chat_rollout_events")
    op.drop_table("chat_rollout_events")
    op.drop_table("chat_rollout_state")
