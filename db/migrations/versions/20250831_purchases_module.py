"""purchases module tables

Revision ID: 20250831_purchases_module
Revises: 20250829_products_prefs_and_price_history
Create Date: 2025-08-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_purchases_module"
down_revision = "20250829_products_prefs_and_price_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("remito_number", sa.String(64), nullable=False),
        sa.Column("remito_date", sa.Date(), nullable=False),
        sa.Column("depot_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="BORRADOR"),
        sa.Column("global_discount", sa.Numeric(6,2), nullable=True, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5,2), nullable=True, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("supplier_id", "remito_number", name="ux_purchases_supplier_remito"),
    )
    op.create_check_constraint("ck_purchases_status", "purchases", "status IN ('BORRADOR','VALIDADA','CONFIRMADA','ANULADA')")

    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_item_id", sa.Integer(), sa.ForeignKey("supplier_products.id"), nullable=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("supplier_sku", sa.String(120), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("qty", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("line_discount", sa.Numeric(6,2), nullable=True, server_default="0"),
        sa.Column("state", sa.String(24), nullable=False, server_default="OK"),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_check_constraint("ck_purchase_lines_state", "purchase_lines", "state IN ('OK','SIN_VINCULAR','PENDIENTE_CREACION')")

    op.create_table(
        "purchase_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("purchase_attachments")
    op.drop_constraint("ck_purchase_lines_state", "purchase_lines", type_="check")
    op.drop_table("purchase_lines")
    op.drop_constraint("ck_purchases_status", "purchases", type_="check")
    op.drop_table("purchases")
