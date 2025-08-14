"""initial schema"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


status_enum = sa.Enum("active", "draft", "archived", name="statusenum")


def upgrade() -> None:
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id")),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku_root", sa.String(), unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("brand", sa.String()),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
        sa.Column("description_html", sa.Text()),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String()),
        sa.Column("value", sa.String()),
        sa.Column("barcode", sa.String()),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("promo_price", sa.Numeric(12, 2)),
        sa.Column("weight_kg", sa.Numeric(10, 3)),
        sa.Column("length_cm", sa.Numeric(10, 2)),
        sa.Column("width_cm", sa.Numeric(10, 2)),
        sa.Column("height_cm", sa.Numeric(10, 2)),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_variants_sku", "variants", ["sku"], unique=True)
    op.create_index("ix_variants_product_id_status", "variants", ["product_id", "status"], unique=False)

    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("alt", sa.String()),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("variants.id"), nullable=False),
        sa.Column("warehouse", sa.String(), nullable=False, server_default="default"),
        sa.Column("stock_qty", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_inventory_variant_warehouse", "inventory", ["variant_id", "warehouse"])

    op.create_table(
        "product_tags",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_unique_constraint("uq_product_tag", "product_tags", ["product_id", "tag_id"])

    op.create_table(
        "variant_prices",
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("variants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_list_id", sa.Integer(), sa.ForeignKey("price_lists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_unique_constraint("uq_variant_price", "variant_prices", ["variant_id", "price_list_id"])


def downgrade() -> None:
    op.drop_constraint("uq_variant_price", "variant_prices", type_="unique")
    op.drop_table("variant_prices")
    op.drop_table("price_lists")

    op.drop_table("product_tags")
    op.drop_table("tags")

    op.drop_constraint("uq_inventory_variant_warehouse", "inventory", type_="unique")
    op.drop_table("inventory")

    op.drop_table("images")
    op.drop_index("ix_variants_product_id_status", table_name="variants")
    op.drop_index("ix_variants_sku", table_name="variants")
    op.drop_table("variants")

    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_index("ix_products_slug", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")

    status_enum.drop(op.get_bind(), checkfirst=True)
