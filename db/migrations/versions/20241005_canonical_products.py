"""add canonical products and equivalences"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20241005_canonical_products'
down_revision = '20240818_import_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'canonical_products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ng_sku', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('specs_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint('uq_canonical_ng_sku', 'canonical_products', ['ng_sku'])

    op.create_table(
        'product_equivalences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_product_id', sa.Integer(), nullable=False),
        sa.Column('canonical_product_id', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.ForeignKeyConstraint(['supplier_product_id'], ['supplier_products.id']),
        sa.ForeignKeyConstraint(['canonical_product_id'], ['canonical_products.id']),
    )
    op.create_unique_constraint(
        'uq_equiv_supplier_product',
        'product_equivalences',
        ['supplier_id', 'supplier_product_id'],
    )
    op.create_index(
        'ix_equiv_canonical_product_id',
        'product_equivalences',
        ['canonical_product_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_equiv_canonical_product_id', table_name='product_equivalences')
    op.drop_constraint('uq_equiv_supplier_product', 'product_equivalences', type_='unique')
    op.drop_table('product_equivalences')
    op.drop_constraint('uq_canonical_ng_sku', 'canonical_products', type_='unique')
    op.drop_table('canonical_products')
