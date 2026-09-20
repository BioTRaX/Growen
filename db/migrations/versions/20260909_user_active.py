#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260909_user_active.py
# NG-HEADER: Ubicación: db/migrations/versions/20260909_user_active.py
# NG-HEADER: Descripción: Permite desactivar usuarios e invalidar sus sesiones de forma explícita.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260909_user_active"
down_revision = "20260905_meli_scopes_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM users WHERE is_active = false")).scalar_one():
        raise RuntimeError("user_active_downgrade_would_reactivate_users")
    op.drop_column("users", "is_active")
