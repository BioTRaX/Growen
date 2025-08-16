from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241010_add_stock_column'
down_revision = '20241005_canonical_products'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('products', sa.Column('stock', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('products', 'stock', server_default=None)


def downgrade() -> None:
    op.drop_column('products', 'stock')
