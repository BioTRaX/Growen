# NG-HEADER: Nombre de archivo: 20251130_sales_channels_and_costs.py
# NG-HEADER: Ubicación: db/migrations/versions/20251130_sales_channels_and_costs.py
# NG-HEADER: Descripción: Migración para agregar SalesChannel y campos channel_id/additional_costs a Sale
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""sales_channels_and_costs

Revision ID: 20251130_sales_channels
Revises: 155b54f2528b
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251130_sales_channels'
down_revision = '155b54f2528b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear tabla sales_channels
    op.create_table(
        'sales_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Agregar columnas a sales
    op.add_column('sales', sa.Column('channel_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('additional_costs', sa.JSON(), nullable=True))
    # Agregar columna meta si no existe
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('sales')]
    if 'meta' not in columns:
        op.add_column('sales', sa.Column('meta', sa.JSON(), nullable=True))

    # Crear FK channel_id -> sales_channels
    op.create_foreign_key(
        'fk_sales_channel_id',
        'sales',
        'sales_channels',
        ['channel_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Crear índice para channel_id (consultas frecuentes por canal)
    op.create_index('ix_sales_channel_id', 'sales', ['channel_id'])


def downgrade() -> None:
    # Eliminar índice
    op.drop_index('ix_sales_channel_id', table_name='sales')

    # Eliminar FK
    op.drop_constraint('fk_sales_channel_id', 'sales', type_='foreignkey')

    # Eliminar columnas de sales
    op.drop_column('sales', 'additional_costs')
    op.drop_column('sales', 'channel_id')

    # Eliminar tabla sales_channels
    op.drop_table('sales_channels')

