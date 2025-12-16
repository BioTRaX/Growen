# NG-HEADER: Nombre de archivo: history.py
# NG-HEADER: Ubicación: services/chat/history.py
# NG-HEADER: Descripción: Servicio de persistencia y recuperación de historial de chat
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio para gestionar el historial de conversaciones del chatbot.

Permite guardar mensajes y recuperar el contexto reciente de una sesión,
habilitando memoria conversacional para el agente.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from db.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


async def get_or_create_session(
    db: AsyncSession,
    session_id: str,
    user_identifier: Optional[str] = None
) -> ChatSession:
    """
    Obtiene una sesión existente o crea una nueva si no existe.
    
    Args:
        db: Sesión de base de datos async
        session_id: Identificador de la sesión (ej: "telegram:12345")
        user_identifier: Identificador del usuario (si no se proporciona, se extrae del session_id)
        
    Returns:
        Instancia de ChatSession (existente o creada)
        
    Raises:
        ValueError: Si hay un error al crear la sesión (ej: constraint violation)
    """
    try:
        # Buscar sesión existente
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        result = await db.execute(stmt)
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            return existing_session
        
        # Crear nueva sesión
        if not user_identifier:
            # Extraer user_identifier del session_id
            if session_id.startswith("telegram:"):
                user_identifier = session_id[9:]  # "telegram:12345" -> "12345"
            elif session_id.startswith("web:"):
                user_identifier = session_id[4:]  # "web:abc123" -> "abc123"
            else:
                user_identifier = session_id  # Usar el session_id completo como fallback
        
        new_session = ChatSession(
            session_id=session_id,
            user_identifier=user_identifier,
            status="new",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_session)
        await db.flush()
        logger.debug(f"Creada nueva sesión: {session_id[:20]}...")
        return new_session
    except IntegrityError as e:
        logger.error(f"Error de integridad al crear sesión {session_id[:20]}...: {e}")
        # Puede ser que la sesión se creó en paralelo, intentar obtenerla de nuevo
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        result = await db.execute(stmt)
        existing_session = result.scalar_one_or_none()
        if existing_session:
            logger.debug(f"Sesión encontrada tras error de integridad: {session_id[:20]}...")
            return existing_session
        raise ValueError(f"No se pudo crear la sesión {session_id}: {e}") from e
    except Exception as e:
        logger.error(f"Error inesperado al crear sesión {session_id[:20]}...: {type(e).__name__}: {e}")
        raise ValueError(f"No se pudo crear la sesión {session_id}: {e}") from e


async def save_message(
    session: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
    user_identifier: Optional[str] = None
) -> ChatMessage:
    """
    Guarda un mensaje en el historial de chat y actualiza la sesión asociada.
    
    Crea o actualiza la ChatSession si es necesario y actualiza last_message_at.
    
    Args:
        session: Sesión de base de datos async
        session_id: Identificador de la sesión de chat (UUID o similar, ej: "telegram:12345")
        role: Rol del mensaje ("user", "assistant", "tool", "system")
        content: Contenido del mensaje
        metadata: Metadatos opcionales (ej: tool_name, tokens, intent)
        user_identifier: Identificador del usuario (opcional, se extrae del session_id si no se proporciona)
        
    Returns:
        Instancia de ChatMessage creada
        
    Raises:
        ValueError: Si hay un error al guardar el mensaje o crear la sesión
        
    Example:
        >>> await save_message(
        ...     session=session,
        ...     session_id="telegram:12345",
        ...     role="user",
        ...     content="¿Cuál es el precio del sustrato Growmix?",
        ...     metadata={"intent": "product_query"}
        ... )
    """
    try:
        # Asegurar que la sesión existe
        chat_session = await get_or_create_session(session, session_id, user_identifier)
        
        # Validar role
        if role not in ("user", "assistant", "tool", "system"):
            logger.warning(f"Role inválido '{role}' en session {session_id[:20]}..., usando 'user'")
            role = "user"
        
        # Crear el mensaje
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow(),
            meta=metadata or {}
        )
        session.add(message)
        await session.flush()
        
        # Actualizar last_message_at de la sesión
        chat_session.last_message_at = datetime.utcnow()
        chat_session.updated_at = datetime.utcnow()
        await session.flush()
        
        logger.debug(f"Mensaje guardado: session={session_id[:20]}..., role={role}, content_length={len(content)}")
        return message
        
    except IntegrityError as e:
        logger.error(f"Error de integridad al guardar mensaje en {session_id[:20]}...: {e}")
        # Puede ser constraint violation (ej: FK inválido, duplicado)
        await session.rollback()
        # Intentar recuperar la sesión y volver a intentar
        try:
            chat_session = await get_or_create_session(session, session_id, user_identifier)
            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                created_at=datetime.utcnow(),
                meta=metadata or {}
            )
            session.add(message)
            chat_session.last_message_at = datetime.utcnow()
            chat_session.updated_at = datetime.utcnow()
            await session.flush()
            logger.info(f"Mensaje guardado exitosamente tras reintento: {session_id[:20]}...")
            return message
        except Exception as retry_error:
            logger.error(f"Error en reintento de guardado: {retry_error}")
            raise ValueError(f"No se pudo guardar el mensaje en {session_id}: {e}") from e
    except Exception as e:
        logger.error(f"Error inesperado al guardar mensaje en {session_id[:20]}...: {type(e).__name__}: {e}")
        await session.rollback()
        raise ValueError(f"No se pudo guardar el mensaje en {session_id}: {e}") from e


async def get_recent_history(
    session: AsyncSession,
    session_id: str,
    limit: int = 6
) -> str:
    """
    Recupera el historial reciente de una sesión y lo formatea para inyectar en el prompt.
    
    Args:
        session: Sesión de base de datos async
        session_id: Identificador de la sesión de chat
        limit: Número máximo de mensajes a recuperar (default: 6, últimos 3 intercambios)
        
    Returns:
        String formateado con el historial en orden cronológico:
        ```
        H: Usuario: Hola
        H: Asistente: Hola, ¿en qué puedo ayudarte?
        H: Usuario: Info de Growmix
        ```
        
    Notes:
        - Solo recupera mensajes con role "user" o "assistant" (filtra "tool" y "system")
        - Ordena cronológicamente (más antiguos primero)
        - Formato "H:" permite al LLM distinguir historial de mensaje actual
        
    Example:
        >>> history = await get_recent_history(session, "abc123", limit=6)
        >>> print(history)
        H: Usuario: ¿Cuál es el precio del sustrato Growmix?
        H: Asistente: El sustrato Growmix Multipro cuesta $X...
        H: Usuario: ¿Cuántos hay en stock?
    """
    # Consultar últimos mensajes (solo user/assistant, no tool/system)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.role.in_(["user", "assistant"]))
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    messages = result.scalars().all()
    
    if not messages:
        return ""
    
    # Revertir orden para que sea cronológico (más antiguo primero)
    messages = list(reversed(messages))
    
    # Formatear historial
    lines = []
    for msg in messages:
        # Mapear role a etiqueta legible
        label = "Usuario" if msg.role == "user" else "Asistente"
        # Limpiar contenido (quitar prefijos tipo "openai:" si existen)
        clean_content = msg.content.replace("openai:", "").strip()
        lines.append(f"H: {label}: {clean_content}")
    
    return "\n".join(lines)


async def get_full_history(
    session: AsyncSession,
    session_id: str,
    limit: Optional[int] = None
) -> list[ChatMessage]:
    """
    Recupera el historial completo de una sesión (todos los roles, sin formatear).
    
    Útil para debugging, exportación de conversaciones o análisis.
    
    Args:
        session: Sesión de base de datos async
        session_id: Identificador de la sesión de chat
        limit: Límite opcional de mensajes (None = todos)
        
    Returns:
        Lista de objetos ChatMessage ordenados cronológicamente
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    
    if limit:
        stmt = stmt.limit(limit)
    
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def clear_session_history(
    session: AsyncSession,
    session_id: str
) -> int:
    """
    Elimina todo el historial de una sesión específica.
    
    Útil para implementar comando "borrar conversación" o limpiar sesiones expiradas.
    
    Args:
        session: Sesión de base de datos async
        session_id: Identificador de la sesión a limpiar
        
    Returns:
        Número de mensajes eliminados
    """
    from sqlalchemy import delete
    
    stmt = delete(ChatMessage).where(ChatMessage.session_id == session_id)
    result = await session.execute(stmt)
    await session.flush()
    
    return result.rowcount or 0
