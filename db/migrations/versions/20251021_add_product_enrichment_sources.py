# NG-HEADER: Nombre de archivo: 20251021_add_product_enrichment_sources.py
# NG-HEADER: Ubicación: db/migrations/versions/20251021_add_product_enrichment_sources.py
# NG-HEADER: Descripción: Agrega columna enrichment_sources_url a products para apuntar al .txt de fuentes.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251021_add_product_enrichment_sources'
down_revision = '20250927_consolidated_base'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.add_column(sa.Column('enrichment_sources_url', sa.String(length=600), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('enrichment_sources_url')
