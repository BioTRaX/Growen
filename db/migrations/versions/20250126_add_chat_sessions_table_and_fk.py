# NG-HEADER: Nombre de archivo: 20250126_add_chat_sessions_table_and_fk.py
# NG-HEADER: Ubicación: db/migrations/versions/20250126_add_chat_sessions_table_and_fk.py
# NG-HEADER: Descripción: Migración Alembic: crea tabla chat_sessions y migra chat_messages a ForeignKey
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add_chat_sessions_table_and_fk

Revision ID: 20250126_chat_sessions
Revises: 155b54f2528b
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20250126_chat_sessions'
down_revision = '155b54f2528b'
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    
    # 1. Crear tabla chat_sessions
    if not _table_exists('chat_sessions'):
        op.create_table(
            'chat_sessions',
            sa.Column('session_id', sa.String(length=100), nullable=False),
            sa.Column('user_identifier', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
            sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
            sa.Column('admin_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('last_message_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('session_id')
        )
        
        # Agregar CheckConstraint para status
        bind.execute(text("""
            ALTER TABLE chat_sessions
            ADD CONSTRAINT ck_chat_sessions_status
            CHECK (status IN ('new','reviewed','archived'))
        """))
        
        # Crear índices
        op.create_index('ix_chat_sessions_user', 'chat_sessions', ['user_identifier'], unique=False)
        op.create_index('ix_chat_sessions_status', 'chat_sessions', ['status'], unique=False)
        op.create_index('ix_chat_sessions_last_message', 'chat_sessions', ['last_message_at'], unique=False)
        op.create_index('ix_chat_sessions_created', 'chat_sessions', ['created_at'], unique=False)
    
    # 2. Migrar datos existentes de chat_messages
    # Agrupar por session_id y crear sesiones
    if _table_exists('chat_messages'):
        # Verificar si hay mensajes
        result = bind.execute(text("SELECT COUNT(*) FROM chat_messages"))
        count = result.scalar()
        
        if count > 0:
            # Crear sesiones para cada session_id único
            # Extraer user_identifier del session_id (ej: "telegram:12345" -> "12345")
            # Si no tiene formato conocido, usar el session_id completo
            bind.execute(text("""
                INSERT INTO chat_sessions (session_id, user_identifier, status, created_at, last_message_at, updated_at)
                SELECT DISTINCT
                    cm.session_id,
                    CASE 
                        WHEN cm.session_id LIKE 'telegram:%' THEN SUBSTRING(cm.session_id FROM 9)
                        WHEN cm.session_id LIKE 'web:%' THEN SUBSTRING(cm.session_id FROM 5)
                        ELSE cm.session_id
                    END as user_identifier,
                    'new' as status,
                    MIN(cm.created_at) as created_at,
                    MAX(cm.created_at) as last_message_at,
                    MAX(cm.created_at) as updated_at
                FROM chat_messages cm
                WHERE NOT EXISTS (
                    SELECT 1 FROM chat_sessions cs WHERE cs.session_id = cm.session_id
                )
                GROUP BY cm.session_id
            """))
    
    # 3. Convertir session_id en chat_messages a ForeignKey
    # Primero, eliminar el índice existente
    if _table_exists('chat_messages'):
        bind.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = 'chat_messages' 
                    AND indexname = 'ix_chat_messages_session'
                ) THEN
                    DROP INDEX ix_chat_messages_session;
                END IF;
            END $$;
        """))
        
        # Agregar ForeignKey constraint
        bind.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'chat_messages_session_id_fkey'
                ) THEN
                    ALTER TABLE chat_messages
                    ADD CONSTRAINT chat_messages_session_id_fkey
                    FOREIGN KEY (session_id) 
                    REFERENCES chat_sessions(session_id) 
                    ON DELETE CASCADE;
                END IF;
            END $$;
        """))
        
        # Recrear el índice
        op.create_index('ix_chat_messages_session', 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    
    # 1. Eliminar ForeignKey de chat_messages
    if _table_exists('chat_messages'):
        # Eliminar índice
        op.drop_index('ix_chat_messages_session', table_name='chat_messages')
        
        # Eliminar constraint
        bind.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'chat_messages_session_id_fkey'
                ) THEN
                    ALTER TABLE chat_messages
                    DROP CONSTRAINT chat_messages_session_id_fkey;
                END IF;
            END $$;
        """))
        
        # Recrear índice sin FK
        op.create_index('ix_chat_messages_session', 'chat_messages', ['session_id'], unique=False)
    
    # 2. Eliminar tabla chat_sessions
    if _table_exists('chat_sessions'):
        # Eliminar constraint
        bind.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'ck_chat_sessions_status'
                ) THEN
                    ALTER TABLE chat_sessions
                    DROP CONSTRAINT ck_chat_sessions_status;
                END IF;
            END $$;
        """))
        op.drop_index('ix_chat_sessions_created', table_name='chat_sessions')
        op.drop_index('ix_chat_sessions_last_message', table_name='chat_sessions')
        op.drop_index('ix_chat_sessions_status', table_name='chat_sessions')
        op.drop_index('ix_chat_sessions_user', table_name='chat_sessions')
        op.drop_table('chat_sessions')

