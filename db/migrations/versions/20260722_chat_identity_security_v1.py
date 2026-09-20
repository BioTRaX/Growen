#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260722_chat_identity_security_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260722_chat_identity_security_v1.py
# NG-HEADER: Descripción: Identidades externas cifradas y deduplicación Telegram.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Identidades externas cifradas y deduplicación Telegram."""

from alembic import op
import sqlalchemy as sa

revision = "20260722_chat_identity_security_v1"
down_revision = "20260721_market_observability_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El identificador de revisión solicitado supera el VARCHAR(32) que Alembic
    # crea por defecto. Ampliarlo antes de que Alembic persista este revision id.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(32),
            type_=sa.String(64),
            existing_nullable=False,
        )
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_id_ciphertext", sa.Text(), nullable=False),
        sa.Column("external_id_hmac", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_approval"),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_approval','active','revoked')", name="ck_external_identities_status"),
        sa.UniqueConstraint("provider", "external_id_hmac", name="uq_external_identity_provider_hmac"),
    )
    op.create_index("ix_external_identities_user_status", "external_identities", ["user_id", "status"])
    op.create_index(
        "uq_external_identity_active_user_provider",
        "external_identities",
        ["user_id", "provider"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND status IN ('active','pending_approval')"),
    )
    op.create_table(
        "external_identity_link_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("external_identity_id", sa.Integer(), sa.ForeignKey("external_identities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending','consumed','expired')", name="ck_external_identity_link_status"),
        sa.UniqueConstraint("token_hash", name="uq_external_identity_link_token_hash"),
    )
    op.create_index("ix_external_identity_link_user_status", "external_identity_link_requests", ["user_id", "status"])
    op.create_table(
        "telegram_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_id_hash", sa.String(64), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processing_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('queued','processing','succeeded','failed','skipped')", name="ck_telegram_updates_status"),
        sa.UniqueConstraint("bot_id_hash", "update_id", name="uq_telegram_update_bot_update"),
    )
    op.create_index("ix_telegram_updates_status_received", "telegram_updates", ["status", "received_at"])
    op.add_column("chat_sessions", sa.Column("external_identity_id", sa.Integer(), nullable=True))
    op.add_column("chat_sessions", sa.Column("subject_hmac", sa.String(64), nullable=True))
    op.add_column("chat_sessions", sa.Column("conversation_key", sa.String(64), nullable=True))
    op.create_foreign_key("fk_chat_sessions_external_identity", "chat_sessions", "external_identities", ["external_identity_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_chat_sessions_conversation_key", "chat_sessions", ["conversation_key"])
    op.create_index("ix_chat_sessions_channel_subject", "chat_sessions", ["channel", "subject_hmac"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("external_identities", "telegram_updates"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Downgrade bloqueado: existe trazabilidad de identidad o Telegram")
    op.drop_index("ix_chat_sessions_channel_subject", table_name="chat_sessions")
    op.drop_constraint("uq_chat_sessions_conversation_key", "chat_sessions", type_="unique")
    op.drop_constraint("fk_chat_sessions_external_identity", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "conversation_key")
    op.drop_column("chat_sessions", "subject_hmac")
    op.drop_column("chat_sessions", "external_identity_id")
    op.drop_table("telegram_updates")
    op.drop_table("external_identity_link_requests")
    op.drop_index("uq_external_identity_active_user_provider", table_name="external_identities")
    op.drop_table("external_identities")
