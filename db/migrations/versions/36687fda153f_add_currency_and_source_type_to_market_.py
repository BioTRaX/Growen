#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 36687fda153f_add_currency_and_source_type_to_market_.py
# NG-HEADER: Ubicación: db/migrations/versions/36687fda153f_add_currency_and_source_type_to_market_.py
# NG-HEADER: Descripción: Agrega campos currency y source_type a market_sources
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add currency and source_type to market_sources

Revision ID: 36687fda153f
Revises: a219fcd042ea
Create Date: 2025-11-11 20:11:30.247990
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '36687fda153f'
down_revision = 'a219fcd042ea'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Detectar dialecto de la base de datos
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    # Agregar campos a market_sources con batch_alter_table para compatibilidad SQLite
    with op.batch_alter_table('market_sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(length=10), nullable=True, server_default='ARS'))
        
        # En PostgreSQL usar ENUM, en SQLite usar String
        if dialect_name == 'postgresql':
            # Crear enum para source_type
            source_type_enum = postgresql.ENUM('static', 'dynamic', name='source_type_enum', create_type=False)
            source_type_enum.create(bind, checkfirst=True)
            batch_op.add_column(sa.Column('source_type', postgresql.ENUM('static', 'dynamic', name='source_type_enum', create_type=False), nullable=True, server_default='static'))
        else:
            # SQLite: usar String
            batch_op.add_column(sa.Column('source_type', sa.String(length=20), nullable=True, server_default='static'))

def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    # Eliminar campos agregados
    with op.batch_alter_table('market_sources', schema=None) as batch_op:
        batch_op.drop_column('source_type')
        batch_op.drop_column('currency')
    
    # Eliminar enum solo en PostgreSQL
    if dialect_name == 'postgresql':
        source_type_enum = postgresql.ENUM('static', 'dynamic', name='source_type_enum')
        source_type_enum.drop(bind, checkfirst=True)

