# NG-HEADER: Nombre de archivo: 20250918_sales_and_customers.py
# NG-HEADER: Ubicación: db/migrations/versions/20250918_sales_and_customers.py
# NG-HEADER: Descripción: Crea tablas de clientes y ventas (sales)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""sales and customers tables

Revision ID: 20250918_sales_and_customers
Revises: 20250914_extend_supplier_files
Create Date: 2025-09-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250918_sales_and_customers"
down_revision = "20250914_extend_supplier_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("doc_id", sa.String(32), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="ux_customers_email"),
        sa.UniqueConstraint("doc_id", name="ux_customers_doc"),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="CONFIRMADA"),
        sa.Column("sale_date", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("total_amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("paid_total", sa.Numeric(12,2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint("ck_sales_status", "sales", "status IN ('BORRADOR','CONFIRMADA','ANULADA')")

    op.create_table(
        "sale_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("line_discount", sa.Numeric(6,2), nullable=True, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
    )

    op.create_table(
        "sale_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="efectivo"),
        sa.Column("amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_check_constraint("ck_sale_payments_method", "sale_payments", "method IN ('efectivo','debito','credito','transferencia','mercadopago','otro')")

    op.create_table(
        "sale_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("sale_attachments")
    op.drop_constraint("ck_sale_payments_method", "sale_payments", type_="check")
    op.drop_table("sale_payments")
    op.drop_table("sale_lines")
    op.drop_constraint("ck_sales_status", "sales", type_="check")
    op.drop_table("sales")
    op.drop_table("customers")
