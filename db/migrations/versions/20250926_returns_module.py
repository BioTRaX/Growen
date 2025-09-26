#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250926_returns_module.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_returns_module.py
# NG-HEADER: Descripción: Crea tablas de devoluciones (returns, return_lines)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""returns module

Revision ID: 20250926_returns_module
Revises: 20250925_extend_sales_customers_fields
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250926_returns_module"
down_revision = "20250925_extend_sales_customers_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="REGISTRADA"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_returns_status", "returns", "status IN ('BORRADOR','REGISTRADA','ANULADA')"
    )
    op.create_index("ix_returns_sale_id", "returns", ["sale_id"], unique=False)

    op.create_table(
        "return_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("returns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_line_id", sa.Integer(), sa.ForeignKey("sale_lines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_return_lines_return_id", "return_lines", ["return_id"], unique=False)
    op.create_index("ix_return_lines_product_id", "return_lines", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_return_lines_product_id", table_name="return_lines")
    op.drop_index("ix_return_lines_return_id", table_name="return_lines")
    op.drop_table("return_lines")
    op.drop_index("ix_returns_sale_id", table_name="returns")
    op.drop_constraint("ck_returns_status", "returns", type_="check")
    op.drop_table("returns")
