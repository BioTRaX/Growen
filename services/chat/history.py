# NG-HEADER: Nombre de archivo: history.py
# NG-HEADER: Ubicación: services/chat/history.py
# NG-HEADER: Descripción: Servicio de persistencia y recuperación de historial de chat
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Servicio para gestionar el historial de conversaciones del chatbot.

Permite guardar mensajes y recuperar el contexto reciente de una sesión,
habilitando memoria conversacional para el agente.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChatMessage


async def save_message(
    session: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None
) -> ChatMessage:
    """
    Guarda un mensaje en el historial de chat.
    
    Args:
        session: Sesión de base de datos async
        session_id: Identificador de la sesión de chat (UUID o similar)
        role: Rol del mensaje ("user", "assistant", "tool", "system")
        content: Contenido del mensaje
        metadata: Metadatos opcionales (ej: tool_name, tokens, intent)
        
    Returns:
        Instancia de ChatMessage creada
        
    Example:
        >>> await save_message(
        ...     session=session,
        ...     session_id="abc123",
        ...     role="user",
        ...     content="¿Cuál es el precio del sustrato Growmix?",
        ...     metadata={"intent": "product_query"}
        ... )
    """
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.utcnow(),
        meta=metadata or {}
    )
    session.add(message)
    await session.flush()  # Para obtener el ID si es necesario
    return message


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
