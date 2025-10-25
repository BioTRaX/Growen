# NG-HEADER: Nombre de archivo: 20251025_add_products_is_enriching.py
# NG-HEADER: Ubicación: db/migrations/versions/20251025_add_products_is_enriching.py
# NG-HEADER: Descripción: Agrega columna is_enriching a products (boolean, default false)
# NG-HEADER: Lineamientos: Ver AGENTS.md

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251025_add_products_is_enriching'
down_revision = '20251021_add_product_enrichment_trace'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Detectar si la columna ya existe para evitar fallas en entornos aplicados manualmente
    has_col = False
    try:
        res = conn.exec_driver_sql("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='products' AND column_name='is_enriching'
        """)
        has_col = res.first() is not None
    except Exception:
        has_col = False
    if not has_col:
        op.add_column('products', sa.Column('is_enriching', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        # Opcional: quitar server_default para futuras inserciones si queremos delegar al ORM
        try:
            op.alter_column('products', 'is_enriching', server_default=None)
        except Exception:
            pass


def downgrade() -> None:
    # Quitar la columna si existe
    conn = op.get_bind()
    try:
        res = conn.exec_driver_sql("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='products' AND column_name='is_enriching'
        """)
        if res.first() is not None:
            op.drop_column('products', 'is_enriching')
    except Exception:
        # En downgrade, tolerar errores
        pass
