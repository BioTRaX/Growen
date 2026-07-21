#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260718_admin_jsonb_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20260718_admin_jsonb_v2.py
# NG-HEADER: Descripción: Alinea metadatos operativos administrativos con JSONB en PostgreSQL.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Alinea los campos JSON administrativos con JSONBCompat del ORM.

Revision ID: 20260718_admin_jsonb_v2
Revises: 20260718_admin_operations_v1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260718_admin_jsonb_v2"
down_revision = "20260718_admin_operations_v1"
branch_labels = None
depends_on = None


JSON_COLUMNS = (
    ("chat_sessions", "problem_signals"),
    ("drive_sync_runs", "meta"),
    ("drive_sync_items", "meta"),
    ("scheduler_runs", "config_snapshot"),
    ("knowledge_index_tasks", "result"),
    ("catalog_generation_events", "payload"),
    ("chat_message_feedback", "categories"),
    ("ai_prompt_versions", "metrics"),
    ("ai_prompt_evaluations", "details"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    for table, column in JSON_COLUMNS:
        if inspector.has_table(table) and column in {item["name"] for item in inspector.get_columns(table)}:
            op.alter_column(
                table,
                column,
                existing_type=sa.JSON(),
                type_=postgresql.JSONB(astext_type=sa.Text()),
                postgresql_using=f"{column}::jsonb",
            )


def downgrade() -> None:
    raise RuntimeError("Downgrade bloqueado: convertir JSONB a JSON altera contratos operativos")
