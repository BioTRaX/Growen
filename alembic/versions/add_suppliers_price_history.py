"""add suppliers and price history tables"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = 'add_suppliers_price_history'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('slug', sa.String(50), unique=True),
        sa.Column('name', sa.String(100)),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'supplier_files',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('supplier_id', sa.Integer, sa.ForeignKey('suppliers.id')),
        sa.Column('filename', sa.String(200)),
        sa.Column('sha256', sa.String(64)),
        sa.Column('rows', sa.Integer),
        sa.Column('uploaded_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('processed', sa.Boolean, default=False),
        sa.Column('dry_run', sa.Boolean, default=True),
        sa.Column('notes', sa.Text),
    )
    op.create_table(
        'supplier_products',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('supplier_id', sa.Integer, sa.ForeignKey('suppliers.id')),
        sa.Column('supplier_product_id', sa.String(100)),
        sa.Column('title', sa.String(200)),
        sa.Column('category_level_1', sa.String(100)),
        sa.Column('category_level_2', sa.String(100)),
        sa.Column('category_level_3', sa.String(100)),
        sa.Column('min_purchase_qty', sa.Numeric(10,2)),
        sa.Column('current_purchase_price', sa.Numeric(10,2)),
        sa.Column('current_sale_price', sa.Numeric(10,2)),
        sa.Column('last_seen_at', sa.DateTime),
        sa.Column('internal_product_id', sa.Integer, sa.ForeignKey('products.id')),
        sa.Column('internal_variant_id', sa.Integer, sa.ForeignKey('variants.id')),
        sa.UniqueConstraint('supplier_id', 'supplier_product_id'),
    )
    op.create_table(
        'supplier_price_history',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('supplier_product_fk', sa.Integer, sa.ForeignKey('supplier_products.id')),
        sa.Column('file_fk', sa.Integer, sa.ForeignKey('supplier_files.id')),
        sa.Column('as_of_date', sa.Date),
        sa.Column('purchase_price', sa.Numeric(10,2)),
        sa.Column('sale_price', sa.Numeric(10,2)),
        sa.Column('delta_purchase_pct', sa.Numeric(10,2)),
        sa.Column('delta_sale_pct', sa.Numeric(10,2)),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('supplier_price_history')
    op.drop_table('supplier_products')
    op.drop_table('supplier_files')
    op.drop_table('suppliers')
