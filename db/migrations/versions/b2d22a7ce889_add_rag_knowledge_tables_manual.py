"""add_rag_knowledge_tables_manual

Revision ID: b2d22a7ce889
Revises: c0467ef5320e
Create Date: 2025-11-25 18:59:39.280509
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision = 'b2d22a7ce889'
down_revision = 'c0467ef5320e'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Crear tabla knowledge_sources
    op.create_table(
        'knowledge_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('meta_json', postgresql.JSONB(), server_default='{}', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_sources_created', 'knowledge_sources', ['created_at'], unique=False)
    op.create_index('ix_knowledge_sources_hash', 'knowledge_sources', ['hash'], unique=False)
    
    # Crear tabla knowledge_chunks
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column('chunk_metadata', postgresql.JSONB(), server_default='{}', nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_chunks_source', 'knowledge_chunks', ['source_id'], unique=False)
    
    # Nota: El índice IVFFlat en embedding se creará manualmente después de insertar datos
    # op.create_index('ix_knowledge_chunks_embedding', 'knowledge_chunks', ['embedding'], 
    #                 unique=False, postgresql_using='ivfflat')

def downgrade() -> None:
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_sources')
