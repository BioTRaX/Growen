"""user prefs, price history, audit, canonical sale_price

Revision ID: 20250829_products_prefs_and_price_history
Revises: 20250825_canonical_ng_sku_nullable
Create Date: 2025-08-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250829_products_prefs_and_price_history"
down_revision = "20250825_canonical_ng_sku_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sale_price to canonical_products if missing
    with op.batch_alter_table("canonical_products") as batch:
        try:
            batch.add_column(sa.Column("sale_price", sa.Numeric(12,2), nullable=True))
        except Exception:
            pass

    # user_preferences
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("data", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ux_user_preferences_user_scope", "user_preferences", ["user_id","scope"], unique=True)

    # price_history
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("price_old", sa.Numeric(12,2), nullable=False),
        sa.Column("price_new", sa.Numeric(12,2), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("table", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("price_history")
    op.drop_index("ux_user_preferences_user_scope", table_name="user_preferences")
    op.drop_table("user_preferences")
    with op.batch_alter_table("canonical_products") as batch:
        try:
            batch.drop_column("sale_price")
        except Exception:
            pass
