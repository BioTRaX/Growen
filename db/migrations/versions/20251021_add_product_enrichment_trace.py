# NG-HEADER: Nombre de archivo: 20251021_add_product_enrichment_trace.py
# NG-HEADER: Ubicación: db/migrations/versions/20251021_add_product_enrichment_trace.py
# NG-HEADER: Descripción: Agrega columnas de trazabilidad de enriquecimiento (last_enriched_at, enriched_by) en products.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251021_add_product_enrichment_trace'
down_revision = '20251021_add_product_technical_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.add_column(sa.Column('last_enriched_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('enriched_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_products_enriched_by_users', 'users', ['enriched_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        try:
            batch_op.drop_constraint('fk_products_enriched_by_users', type_='foreignkey')
        except Exception:
            # tolerar si el constraint no existe (según backend)
            pass
        batch_op.drop_column('enriched_by')
        batch_op.drop_column('last_enriched_at')
