"""add_product_specs_and_usage

Revision ID: 20251119_add_product_specs_and_usage
Revises: 20251025_add_products_is_enriching
Create Date: 2025-11-19 23:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251119_add_product_specs_and_usage'
down_revision = '20251025_add_products_is_enriching'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Agregar campos JSONB para especificaciones técnicas e instrucciones de uso en productos."""
    # Agregar technical_specs: dimensiones, potencia, peso, materiales, etc.
    op.add_column('products', sa.Column(
        'technical_specs',
        postgresql.JSONB(astext_type=sa.Text()),
        server_default='{}',
        nullable=True
    ))
    
    # Agregar usage_instructions: pasos de uso, consejos, advertencias
    op.add_column('products', sa.Column(
        'usage_instructions',
        postgresql.JSONB(astext_type=sa.Text()),
        server_default='{}',
        nullable=True
    ))


def downgrade() -> None:
    """Revertir cambios eliminando los campos agregados."""
    op.drop_column('products', 'usage_instructions')
    op.drop_column('products', 'technical_specs')
