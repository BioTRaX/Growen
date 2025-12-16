#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: archive_old_chat_sessions.py
# NG-HEADER: Ubicación: scripts/archive_old_chat_sessions.py
# NG-HEADER: Descripción: Script para archivar automáticamente sesiones de chat antiguas sin actividad
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""Script para archivar automáticamente sesiones de chat sin actividad.

Archiva sesiones que:
- Tienen status='new' o 'reviewed'
- No tienen mensajes en los últimos N días (configurable, default: 90 días)
- No tienen admin_notes (para preservar sesiones marcadas para revisión)

Uso:
    python scripts/archive_old_chat_sessions.py
    python scripts/archive_old_chat_sessions.py --days 60  # Archivar sesiones sin actividad en 60 días
    python scripts/archive_old_chat_sessions.py --dry-run  # Solo mostrar qué se archivaría
"""

import asyncio
import argparse
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importar configuración
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core.config import settings
from db.models import ChatSession, ChatMessage

# Construir DB URL
DB_URL = os.getenv("DB_URL") or settings.db_url


async def archive_old_sessions(days: int = 90, dry_run: bool = False):
    """
    Archiva sesiones de chat sin actividad.
    
    Args:
        days: Días sin actividad antes de archivar (default: 90)
        dry_run: Si True, solo muestra qué se archivaría sin hacer cambios
    """
    engine = create_async_engine(DB_URL, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        async with async_session() as session:
            # Buscar sesiones candidatas:
            # - Status 'new' o 'reviewed'
            # - last_message_at < cutoff_date (o NULL y created_at < cutoff_date)
            # - Sin admin_notes (preservar sesiones marcadas)
            
            # Subquery para obtener última fecha de mensaje por sesión
            from sqlalchemy import func as sql_func
            last_message_subq = (
                select(
                    ChatMessage.session_id,
                    sql_func.max(ChatMessage.created_at).label('last_msg_date')
                )
                .group_by(ChatMessage.session_id)
                .subquery()
            )
            
            # Query principal: sesiones a archivar
            stmt = select(ChatSession).where(
                and_(
                    ChatSession.status.in_(['new', 'reviewed']),
                    ChatSession.admin_notes.is_(None),
                    # last_message_at < cutoff O (last_message_at IS NULL AND created_at < cutoff)
                    sql_func.coalesce(
                        ChatSession.last_message_at,
                        ChatSession.created_at
                    ) < cutoff_date
                )
            )
            
            result = await session.execute(stmt)
            sessions_to_archive = result.scalars().all()
            
            count = len(sessions_to_archive)
            
            if dry_run:
                logger.info(f"[DRY RUN] Se archivarían {count} sesiones (sin actividad en los últimos {days} días)")
                if count > 0:
                    logger.info(f"Ejemplo de sesiones a archivar:")
                    for sess in sessions_to_archive[:5]:
                        last_msg = sess.last_message_at or sess.created_at
                        logger.info(f"  - {sess.session_id[:30]}... (último mensaje: {last_msg.isoformat()})")
                return
            
            if count == 0:
                logger.info(f"No hay sesiones para archivar (corte: {cutoff_date.isoformat()})")
                return
            
            # Actualizar status a 'archived'
            session_ids = [sess.session_id for sess in sessions_to_archive]
            update_stmt = (
                update(ChatSession)
                .where(ChatSession.session_id.in_(session_ids))
                .values(status='archived', updated_at=datetime.utcnow())
            )
            
            result = await session.execute(update_stmt)
            await session.commit()
            
            logger.info(f"✓ Archivadas {result.rowcount} sesiones (sin actividad en los últimos {days} días)")
            
    except Exception as e:
        logger.error(f"Error al archivar sesiones: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser(
        description='Archivar sesiones de chat antiguas sin actividad'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Días sin actividad antes de archivar (default: 90)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo mostrar qué se archivaría sin hacer cambios'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Iniciando archivado de sesiones (días sin actividad: {args.days}, dry-run: {args.dry_run})")
    
    await archive_old_sessions(days=args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())

