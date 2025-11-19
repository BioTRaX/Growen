"""add market_price_history table

Revision ID: d53f209c03d1
Revises: 36687fda153f
Create Date: 2025-11-11 20:28:18.395813
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd53f209c03d1'
down_revision = '36687fda153f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Crear tabla market_price_history
    op.create_table(
        'market_price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='ARS'),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('source_name', sa.String(length=200), nullable=True),
        sa.Column('price_change_pct', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['product_id'], ['canonical_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['market_sources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Crear índices para optimización de consultas
    op.create_index('idx_market_price_history_product_id', 'market_price_history', ['product_id'])
    op.create_index('idx_market_price_history_source_id', 'market_price_history', ['source_id'])
    op.create_index('idx_market_price_history_created_at', 'market_price_history', ['created_at'])
    op.create_index('idx_market_price_history_product_date', 'market_price_history', ['product_id', 'created_at'])


def downgrade() -> None:
    # Eliminar índices primero
    op.drop_index('idx_market_price_history_product_date', table_name='market_price_history')
    op.drop_index('idx_market_price_history_created_at', table_name='market_price_history')
    op.drop_index('idx_market_price_history_source_id', table_name='market_price_history')
    op.drop_index('idx_market_price_history_product_id', table_name='market_price_history')
    
    # Eliminar tabla
    op.drop_table('market_price_history')
