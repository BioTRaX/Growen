# NG-HEADER: Nombre de archivo: 20241005_canonical_products.py
# NG-HEADER: Ubicación: db/migrations/versions/20241005_canonical_products.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add canonical products and equivalences"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from db.migrations.util import (
    has_table,
    has_column,
    index_exists,
    unique_constraint_exists,
)

# revision identifiers, used by Alembic.
revision = "20241005_canonical_products"
down_revision = "6f8e298d069b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Tabla de productos canónicos
    if not has_table(bind, "canonical_products"):
        op.create_table(
            "canonical_products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ng_sku", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("brand", sa.String(length=100), nullable=True),
            sa.Column("specs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    if not unique_constraint_exists(bind, "canonical_products", "uq_canonical_ng_sku") and has_column(
        bind, "canonical_products", "ng_sku"
    ):
        op.create_unique_constraint("uq_canonical_ng_sku", "canonical_products", ["ng_sku"])

    # Equivalencias
    if not has_table(bind, "product_equivalences"):
        op.create_table(
            "product_equivalences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("supplier_id", sa.Integer(), nullable=False),
            sa.Column("supplier_product_id", sa.Integer(), nullable=False),
            sa.Column("canonical_product_id", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
            sa.ForeignKeyConstraint(["supplier_product_id"], ["supplier_products.id"]),
            sa.ForeignKeyConstraint(["canonical_product_id"], ["canonical_products.id"]),
        )

    if not unique_constraint_exists(bind, "product_equivalences", "uq_equiv_supplier_product"):
        op.create_unique_constraint(
            "uq_equiv_supplier_product",
            "product_equivalences",
            ["supplier_id", "supplier_product_id"],
        )

    if not index_exists(bind, "product_equivalences", "ix_equiv_canonical_product_id") and has_column(
        bind, "product_equivalences", "canonical_product_id"
    ):
        op.create_index(
            "ix_equiv_canonical_product_id",
            "product_equivalences",
            ["canonical_product_id"],
        )


def downgrade() -> None:
    op.drop_index('ix_equiv_canonical_product_id', table_name='product_equivalences')
    op.drop_constraint('uq_equiv_supplier_product', 'product_equivalences', type_='unique')
    op.drop_table('product_equivalences')
    op.drop_constraint('uq_canonical_ng_sku', 'canonical_products', type_='unique')
    op.drop_table('canonical_products')
