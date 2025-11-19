"""Add MarketAlert table for price variation alerts

Revision ID: add_market_alerts
Revises: 
Create Date: 2025-11-12 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_market_alerts'
down_revision: Union[str, None] = 'd53f209c03d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear tabla market_alerts
    op.create_table(
        'market_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('old_value', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('new_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('delta_percentage', sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('email_sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Crear foreign keys
    op.create_foreign_key(
        'fk_market_alerts_product_id',
        'market_alerts', 'canonical_products',
        ['product_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_market_alerts_resolved_by',
        'market_alerts', 'users',
        ['resolved_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # Crear índices
    op.create_index('idx_market_alerts_product_id', 'market_alerts', ['product_id'])
    op.create_index('idx_market_alerts_created_at', 'market_alerts', ['created_at'])
    op.create_index('idx_market_alerts_resolved', 'market_alerts', ['resolved'])
    op.create_index('idx_market_alerts_product_active', 'market_alerts', ['product_id', 'resolved'])


def downgrade() -> None:
    # Eliminar índices
    op.drop_index('idx_market_alerts_product_active', table_name='market_alerts')
    op.drop_index('idx_market_alerts_resolved', table_name='market_alerts')
    op.drop_index('idx_market_alerts_created_at', table_name='market_alerts')
    op.drop_index('idx_market_alerts_product_id', table_name='market_alerts')
    
    # Eliminar foreign keys
    op.drop_constraint('fk_market_alerts_resolved_by', 'market_alerts', type_='foreignkey')
    op.drop_constraint('fk_market_alerts_product_id', 'market_alerts', type_='foreignkey')
    
    # Eliminar tabla
    op.drop_table('market_alerts')
