# NG-HEADER: Nombre de archivo: 20251021_add_product_technical_fields.py
# NG-HEADER: Ubicación: db/migrations/versions/20251021_add_product_technical_fields.py
# NG-HEADER: Descripción: Agrega campos técnicos (peso y dimensiones, precio de mercado) a products.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251021_add_product_technical_fields'
down_revision = '20251021_add_product_enrichment_sources'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.add_column(sa.Column('weight_kg', sa.Numeric(10, 3), nullable=True))
        batch_op.add_column(sa.Column('height_cm', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('width_cm', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('depth_cm', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('market_price_reference', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('market_price_reference')
        batch_op.drop_column('depth_cm')
        batch_op.drop_column('width_cm')
        batch_op.drop_column('height_cm')
        batch_op.drop_column('weight_kg')
