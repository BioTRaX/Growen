#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260831_meli_sync_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260831_meli_sync_v1.py
# NG-HEADER: Descripción: Persistencia segura y durable para OAuth, webhooks y sincronización MeLi.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260831_meli_sync_v1"
down_revision = "20260828_market_pipeline_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meli_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("seller_id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.String(8), nullable=True),
        sa.Column("scopes", sa.String(500), nullable=True),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("application_id", "seller_id", name="uq_meli_accounts_application_seller"),
        sa.CheckConstraint("status IN ('active','revoked','error')", name="ck_meli_accounts_status"),
    )
    op.create_index("ix_meli_accounts_status_expires", "meli_accounts", ["status", "token_expires_at"])

    op.create_table(
        "meli_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("code_verifier_ciphertext", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.String(800), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_meli_oauth_states_expires_consumed", "meli_oauth_states", ["expires_at", "consumed_at"])

    op.create_table(
        "meli_notifications",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("meli_accounts.id", ondelete="SET NULL")),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("seller_id", sa.BigInteger(), nullable=False),
        sa.Column("topic", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processing_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','processing','succeeded','failed','skipped')",
            name="ck_meli_notifications_status",
        ),
    )
    op.create_index("ix_meli_notifications_status_received", "meli_notifications", ["status", "received_at"])

    op.create_table(
        "meli_item_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("meli_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("variation_id", sa.BigInteger(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_quantity", sa.Numeric(14, 2), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "item_id", "variation_id", name="uq_meli_item_links_target"),
    )
    op.create_index("ix_meli_item_links_product_active", "meli_item_links", ["product_id", "active"])

    op.create_table(
        "meli_sync_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("meli_accounts.id", ondelete="CASCADE")),
        sa.Column("notification_id", sa.String(128), sa.ForeignKey("meli_notifications.id", ondelete="CASCADE")),
        sa.Column("item_link_id", sa.Integer(), sa.ForeignKey("meli_item_links.id", ondelete="CASCADE")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("dedupe_key", name="uq_meli_sync_jobs_dedupe_key"),
        sa.CheckConstraint("kind IN ('notification','stock','reconcile')", name="ck_meli_sync_jobs_kind"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','skipped')", name="ck_meli_sync_jobs_status"),
    )
    op.create_index("ix_meli_sync_jobs_status_created", "meli_sync_jobs", ["status", "created_at"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("meli_sync_jobs", "meli_item_links", "meli_notifications", "meli_oauth_states", "meli_accounts"):
        count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError("Downgrade bloqueado: existen autorizaciones o trazabilidad MeLi")
    op.drop_table("meli_sync_jobs")
    op.drop_table("meli_item_links")
    op.drop_table("meli_notifications")
    op.drop_table("meli_oauth_states")
    op.drop_table("meli_accounts")
