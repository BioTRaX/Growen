"""add_market_price_updated_at_to_canonical_products

Revision ID: a219fcd042ea
Revises: e69f250b8926
Create Date: 2025-11-11 19:44:16.774958
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a219fcd042ea'
down_revision = 'e69f250b8926'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Agregar campo market_price_updated_at a canonical_products
    # Permite rastrear la fecha de última modificación del precio de mercado de referencia
    op.add_column(
        'canonical_products',
        sa.Column('market_price_updated_at', sa.DateTime(), nullable=True)
    )

def downgrade() -> None:
    # Remover campo market_price_updated_at
    op.drop_column('canonical_products', 'market_price_updated_at')
