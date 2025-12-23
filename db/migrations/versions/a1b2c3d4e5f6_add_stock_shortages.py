# NG-HEADER: Nombre de archivo: add_stock_shortages.py
# NG-HEADER: Ubicación: db/migrations/versions/add_stock_shortages.py
# NG-HEADER: Descripción: Migración para crear tabla stock_shortages (faltantes de inventario)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add_stock_shortages

Revision ID: a1b2c3d4e5f6
Revises: 8b243aad8fcb
Create Date: 2025-12-21 11:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8b243aad8fcb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'stock_shortages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(20), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='OPEN'),
        sa.Column('observation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("reason IN ('GIFT','PENDING_SALE','UNKNOWN')", name='ck_stock_shortages_reason'),
        sa.CheckConstraint("status IN ('OPEN','RECONCILED')", name='ck_stock_shortages_status'),
    )
    op.create_index('ix_stock_shortages_product_created', 'stock_shortages', ['product_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_stock_shortages_product_created')
    op.drop_table('stock_shortages')
