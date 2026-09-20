# NG-HEADER: Nombre de archivo: 20260716_purchase_ingestion_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20260716_purchase_ingestion_v2.py
# NG-HEADER: Descripción: Extiende compras para ingesta documental, historial y trazabilidad.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Extiende compras para ingesta documental e historial.

Revision ID: 20260716_purchase_ingestion_v2
Revises: 20260714_schema_integrity
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_purchase_ingestion_v2"
down_revision = "20260714_schema_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchases", sa.Column("documented_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchases", sa.Column("currency", sa.String(3), nullable=False, server_default="ARS"))
    op.add_column("purchases", sa.Column("import_profile", sa.String(64), nullable=True))
    op.add_column("purchases", sa.Column("extraction_meta", sa.JSON(), nullable=True))
    op.add_column("purchases", sa.Column("meta", sa.JSON(), nullable=True))

    op.add_column("purchase_lines", sa.Column("line_vat_rate", sa.Numeric(5, 2), nullable=True))
    op.add_column("purchase_lines", sa.Column("documented_subtotal", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_lines", sa.Column("documented_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_lines", sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True))
    # `meta` existe en instalaciones migradas; se agrega sólo cuando falta.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    line_columns = {column["name"] for column in inspector.get_columns("purchase_lines")}
    if "meta" not in line_columns:
        op.add_column("purchase_lines", sa.Column("meta", sa.JSON(), nullable=True))

    op.add_column("purchase_attachments", sa.Column("original_name", sa.String(255), nullable=True))
    op.add_column("purchase_attachments", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("purchase_attachments", sa.Column("document_type", sa.String(32), nullable=False, server_default="REMITO"))
    op.create_index("ix_purchase_attachments_sha256", "purchase_attachments", ["sha256"], unique=False)
    op.create_index("ix_purchase_lines_product_purchase", "purchase_lines", ["product_id", "purchase_id"], unique=False)
    op.create_index("ix_purchases_supplier_date", "purchases", ["supplier_id", "remito_date"], unique=False)
    op.add_column("supplier_price_history", sa.Column("purchase_id", sa.Integer(), nullable=True))
    op.add_column("supplier_price_history", sa.Column("purchase_line_id", sa.Integer(), nullable=True))
    op.create_foreign_key("supplier_price_history_purchase_id_fkey", "supplier_price_history", "purchases", ["purchase_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("supplier_price_history_purchase_line_id_fkey", "supplier_price_history", "purchase_lines", ["purchase_line_id"], ["id"], ondelete="SET NULL")

    # Las líneas confirmadas son evidencia histórica: una baja de catálogo no debe eliminarlas.
    op.drop_constraint("purchase_lines_supplier_item_id_fkey", "purchase_lines", type_="foreignkey")
    op.drop_constraint("purchase_lines_product_id_fkey", "purchase_lines", type_="foreignkey")
    op.create_foreign_key(
        "purchase_lines_supplier_item_id_fkey", "purchase_lines", "supplier_products",
        ["supplier_item_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "purchase_lines_product_id_fkey", "purchase_lines", "products",
        ["product_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("supplier_price_history_purchase_line_id_fkey", "supplier_price_history", type_="foreignkey")
    op.drop_constraint("supplier_price_history_purchase_id_fkey", "supplier_price_history", type_="foreignkey")
    op.drop_column("supplier_price_history", "purchase_line_id")
    op.drop_column("supplier_price_history", "purchase_id")
    op.drop_constraint("purchase_lines_product_id_fkey", "purchase_lines", type_="foreignkey")
    op.drop_constraint("purchase_lines_supplier_item_id_fkey", "purchase_lines", type_="foreignkey")
    op.create_foreign_key(
        "purchase_lines_product_id_fkey", "purchase_lines", "products",
        ["product_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "purchase_lines_supplier_item_id_fkey", "purchase_lines", "supplier_products",
        ["supplier_item_id"], ["id"], ondelete="CASCADE",
    )
    op.drop_index("ix_purchases_supplier_date", table_name="purchases")
    op.drop_index("ix_purchase_lines_product_purchase", table_name="purchase_lines")
    op.drop_index("ix_purchase_attachments_sha256", table_name="purchase_attachments")
    op.drop_column("purchase_attachments", "document_type")
    op.drop_column("purchase_attachments", "sha256")
    op.drop_column("purchase_attachments", "original_name")
    op.drop_column("purchase_lines", "extraction_confidence")
    op.drop_column("purchase_lines", "documented_total")
    op.drop_column("purchase_lines", "documented_subtotal")
    op.drop_column("purchase_lines", "line_vat_rate")
    op.drop_column("purchases", "meta")
    op.drop_column("purchases", "extraction_meta")
    op.drop_column("purchases", "import_profile")
    op.drop_column("purchases", "currency")
    op.drop_column("purchases", "documented_total")
