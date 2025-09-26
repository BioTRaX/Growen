#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250925_extend_sales_customers_fields.py
# NG-HEADER: Ubicación: db/migrations/versions/20250925_extend_sales_customers_fields.py
# NG-HEADER: Descripción: Extiende clientes y ventas con campos de PRD (descuentos, snapshots, estados, índices)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""extend sales and customers fields

Revision ID: 20250925_extend_sales_customers_fields
Revises: 20250923_merge_heads_supplier_variant_idx_and_canonical_sku
Create Date: 2025-09-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250925_extend_sales_customers_fields"
down_revision = "20250923_merge_heads_supplier_variant_idx_and_canonical_sku"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # customers: document_*, city, province, kind, is_active
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("document_type", sa.String(length=8), nullable=True))
        batch.add_column(sa.Column("document_number", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("province", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("kind", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False))

    # sales: agregar columnas y actualizar constraint de estado
    with op.batch_alter_table("sales") as batch:
        # Nuevos campos de totales/descuentos/metadatos
        batch.add_column(sa.Column("discount_percent", sa.Numeric(6, 2), server_default="0", nullable=False))
        batch.add_column(sa.Column("discount_amount", sa.Numeric(12, 2), server_default="0", nullable=False))
        batch.add_column(sa.Column("subtotal", sa.Numeric(12, 2), server_default="0", nullable=False))
        batch.add_column(sa.Column("tax", sa.Numeric(12, 2), server_default="0", nullable=False))
        batch.add_column(sa.Column("payment_status", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("correlation_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        # Reemplazar check constraint de estados para incluir ENTREGADA
        try:
            batch.drop_constraint("ck_sales_status", type_="check")
        except Exception:
            # Si no existe, continuar.
            pass
        batch.create_check_constraint(
            "ck_sales_status",
            "status IN ('BORRADOR','CONFIRMADA','ENTREGADA','ANULADA')",
        )

    # Índices de rendimiento en sales
    op.create_index("ix_sales_status", "sales", ["status"], unique=False)
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"], unique=False)
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"], unique=False)

    # sale_lines: snapshots, totales, supplier_item_id, state
    with op.batch_alter_table("sale_lines") as batch:
        batch.add_column(sa.Column("title_snapshot", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("sku_snapshot", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("line_discount_percent", sa.Numeric(6, 2), server_default="0", nullable=True))
        batch.add_column(sa.Column("subtotal", sa.Numeric(12, 2), server_default="0", nullable=True))
        batch.add_column(sa.Column("tax", sa.Numeric(12, 2), server_default="0", nullable=True))
        batch.add_column(sa.Column("total", sa.Numeric(12, 2), server_default="0", nullable=True))
        batch.add_column(sa.Column("supplier_item_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("state", sa.String(length=16), server_default="OK", nullable=True))

    # sale_payments: paid_at, meta
    with op.batch_alter_table("sale_payments") as batch:
        batch.add_column(sa.Column("paid_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    # sale_payments
    with op.batch_alter_table("sale_payments") as batch:
        batch.drop_column("meta")
        batch.drop_column("paid_at")

    # sale_lines
    with op.batch_alter_table("sale_lines") as batch:
        batch.drop_column("state")
        batch.drop_column("supplier_item_id")
        batch.drop_column("total")
        batch.drop_column("tax")
        batch.drop_column("subtotal")
        batch.drop_column("line_discount_percent")
        batch.drop_column("sku_snapshot")
        batch.drop_column("title_snapshot")

    # Índices de sales
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_index("ix_sales_sale_date", table_name="sales")
    op.drop_index("ix_sales_status", table_name="sales")

    # sales: constraint y columnas
    with op.batch_alter_table("sales") as batch:
        # Restaurar constraint anterior (sin ENTREGADA)
        try:
            batch.drop_constraint("ck_sales_status", type_="check")
        except Exception:
            pass
        batch.create_check_constraint(
            "ck_sales_status",
            "status IN ('BORRADOR','CONFIRMADA','ANULADA')",
        )
        # Quitar columnas agregadas
        batch.drop_column("metadata")
        batch.drop_column("correlation_id")
        batch.drop_column("payment_status")
        batch.drop_column("tax")
        batch.drop_column("subtotal")
        batch.drop_column("discount_amount")
        batch.drop_column("discount_percent")

    # customers
    with op.batch_alter_table("customers") as batch:
        batch.drop_column("is_active")
        batch.drop_column("kind")
        batch.drop_column("province")
        batch.drop_column("city")
        batch.drop_column("document_number")
        batch.drop_column("document_type")
