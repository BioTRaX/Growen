"""add_chat_messages_table

Revision ID: 155b54f2528b
Revises: fa50a5cba1bb
Create Date: 2025-11-25 20:17:00.833847
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '155b54f2528b'
down_revision = 'fa50a5cba1bb'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Crear tabla chat_messages
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Crear índices
    op.create_index('ix_chat_messages_session', 'chat_messages', ['session_id'], unique=False)
    op.create_index('ix_chat_messages_created', 'chat_messages', ['created_at'], unique=False)

def downgrade() -> None:
    # Eliminar índices
    op.drop_index('ix_chat_messages_created', table_name='chat_messages')
    op.drop_index('ix_chat_messages_session', table_name='chat_messages')
    
    # Eliminar tabla
    op.drop_table('chat_messages')
