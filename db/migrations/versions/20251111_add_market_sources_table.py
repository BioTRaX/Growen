#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20251111_add_market_sources_table.py
# NG-HEADER: Ubicación: db/migrations/versions/20251111_add_market_sources_table.py
# NG-HEADER: Descripción: Agrega tabla market_sources y campo market_price_reference a canonical_products.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Add market_sources table and market_price_reference to canonical_products

Revision ID: 20251111_add_market_sources
Revises: (última migración existente)
Create Date: 2025-11-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251111_add_market_sources'
down_revision = None  # TODO: Actualizar con la última revisión antes de aplicar
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar campo market_price_reference a canonical_products
    with op.batch_alter_table('canonical_products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('market_price_reference', sa.Numeric(precision=12, scale=2), nullable=True))

    # Crear tabla market_sources
    op.create_table(
        'market_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=200), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('last_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('is_mandatory', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['product_id'], ['canonical_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'url', name='uq_market_sources_product_url')
    )
    
    # Crear índice en product_id para búsquedas rápidas
    op.create_index('idx_market_sources_product_id', 'market_sources', ['product_id'])


def downgrade() -> None:
    # Eliminar índice
    op.drop_index('idx_market_sources_product_id', table_name='market_sources')
    
    # Eliminar tabla market_sources
    op.drop_table('market_sources')
    
    # Eliminar campo market_price_reference de canonical_products
    with op.batch_alter_table('canonical_products', schema=None) as batch_op:
        batch_op.drop_column('market_price_reference')
