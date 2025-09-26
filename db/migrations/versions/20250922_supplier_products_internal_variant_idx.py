# NG-HEADER: Nombre de archivo: 20250922_supplier_products_internal_variant_idx.py
# NG-HEADER: Ubicación: db/migrations/versions/20250922_supplier_products_internal_variant_idx.py
# NG-HEADER: Descripción: Índice para acelerar lookups por internal_variant_id en supplier_products
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Agregar índice en supplier_products.internal_variant_id

Revision ID: 20250922_supplier_products_internal_variant_idx
Revises: 20250918_sales_and_customers
Create Date: 2025-09-22
"""
from alembic import op
import sqlalchemy as sa

from db.migrations.util import has_column, index_exists

# Revisar el último head conocido en el repo
revision = "20250922_supplier_products_internal_variant_idx"
down_revision = "20250918_sales_and_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Índice simple sobre internal_variant_id
    if has_column(bind, "supplier_products", "internal_variant_id") and not index_exists(
        bind, "supplier_products", "ix_supplier_products_internal_variant_id"
    ):
        op.create_index(
            "ix_supplier_products_internal_variant_id",
            "supplier_products",
            ["internal_variant_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "supplier_products", "ix_supplier_products_internal_variant_id"):
        op.drop_index("ix_supplier_products_internal_variant_id", table_name="supplier_products")
