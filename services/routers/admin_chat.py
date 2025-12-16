# NG-HEADER: Nombre de archivo: admin_chat.py
# NG-HEADER: Ubicación: services/routers/admin_chat.py
# NG-HEADER: Descripción: Endpoints de administración de sesiones de chat
# NG-HEADER: Lineamientos: Ver AGENTS.md

"""
Router para administración de sesiones de chat.

Endpoints:
- GET /admin/chats - Lista sesiones (paginado, filtros por status)
- GET /admin/chats/{session_id} - Detalle de sesión y mensajes
- PATCH /admin/chats/{session_id} - Actualizar estado/notas/tags
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload

from db.session import get_session
from db.models import ChatSession, ChatMessage
from services.auth import require_roles, SessionData

router = APIRouter(prefix="/admin/chats", tags=["Admin - Chat"])


# ==================== SCHEMAS ====================

class ChatMessageOut(BaseModel):
    """Schema de salida para mensaje de chat."""
    id: int
    role: str
    content: str
    created_at: str
    meta: Optional[dict] = None

    class Config:
        from_attributes = True


class ChatSessionOut(BaseModel):
    """Schema de salida para sesión de chat."""
    session_id: str
    user_identifier: str
    status: str
    tags: Optional[dict] = None
    admin_notes: Optional[str] = None
    created_at: str
    last_message_at: Optional[str] = None
    updated_at: str
    message_count: Optional[int] = None  # Solo en lista

    class Config:
        from_attributes = True


class ChatSessionDetailOut(BaseModel):
    """Schema de salida para detalle completo de sesión."""
    session: ChatSessionOut
    messages: list[ChatMessageOut]


class ChatSessionUpdate(BaseModel):
    """Schema para actualizar sesión."""
    status: Optional[str] = Field(None, description="Status: 'new', 'reviewed', 'archived'")
    admin_notes: Optional[str] = Field(None, description="Notas administrativas")
    tags: Optional[dict] = Field(None, description="Tags JSON")


class ChatSessionsListResponse(BaseModel):
    """Respuesta de lista de sesiones."""
    items: list[ChatSessionOut]
    total: int
    page: int
    page_size: int


# ==================== ENDPOINTS ====================

@router.get("", response_model=ChatSessionsListResponse)
async def list_chat_sessions(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamaño de página"),
    status: Optional[str] = Query(None, description="Filtrar por status (new, reviewed, archived)"),
    user_identifier: Optional[str] = Query(None, description="Buscar por user_identifier (búsqueda parcial)"),
    date_from: Optional[str] = Query(None, description="Fecha desde (ISO format: YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha hasta (ISO format: YYYY-MM-DD)"),
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    """
    Lista sesiones de chat con paginación y filtros.
    
    **Requiere rol**: admin o colaborador
    
    Filtros disponibles:
    - status: Filtrar por estado (new, reviewed, archived)
    - user_identifier: Búsqueda parcial en user_identifier
    - date_from: Filtrar sesiones desde esta fecha (basado en created_at)
    - date_to: Filtrar sesiones hasta esta fecha (basado en created_at)
    """
    # Construir query base
    query = select(ChatSession)
    filters = []
    
    # Aplicar filtro de status si existe
    if status:
        filters.append(ChatSession.status == status)
    
    # Aplicar filtro de user_identifier (búsqueda parcial)
    if user_identifier:
        filters.append(ChatSession.user_identifier.ilike(f"%{user_identifier}%"))
    
    # Aplicar filtros de fecha
    if date_from:
        try:
            date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            filters.append(ChatSession.created_at >= date_from_obj)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de date_from inválido. Usar ISO format: YYYY-MM-DD")
    
    if date_to:
        try:
            date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            # Incluir todo el día (hasta 23:59:59)
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            filters.append(ChatSession.created_at <= date_to_obj)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de date_to inválido. Usar ISO format: YYYY-MM-DD")
    
    # Aplicar todos los filtros
    if filters:
        query = query.where(and_(*filters))
    
    # Contar total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Aplicar paginación y ordenamiento
    offset = (page - 1) * page_size
    query = query.order_by(desc(ChatSession.last_message_at)).offset(offset).limit(page_size)
    
    # Ejecutar query
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    # Obtener conteo de mensajes para cada sesión
    session_ids = [s.session_id for s in sessions]
    message_counts = {}
    if session_ids:
        count_stmt = (
            select(ChatMessage.session_id, func.count(ChatMessage.id).label("count"))
            .where(ChatMessage.session_id.in_(session_ids))
            .group_by(ChatMessage.session_id)
        )
        count_result = await db.execute(count_stmt)
        message_counts = {row.session_id: row.count for row in count_result.all()}
    
    # Construir respuesta
    items = []
    for session in sessions:
        session_dict = {
            "session_id": session.session_id,
            "user_identifier": session.user_identifier,
            "status": session.status,
            "tags": session.tags,
            "admin_notes": session.admin_notes,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "message_count": message_counts.get(session.session_id, 0),
        }
        items.append(ChatSessionOut(**session_dict))
    
    return ChatSessionsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{session_id}", response_model=ChatSessionDetailOut)
async def get_chat_session(
    session_id: str,
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    """
    Obtiene el detalle completo de una sesión de chat incluyendo todos sus mensajes.
    
    **Requiere rol**: admin o colaborador
    """
    # Buscar sesión con mensajes
    stmt = (
        select(ChatSession)
        .where(ChatSession.session_id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")
    
    # Ordenar mensajes por fecha
    messages = sorted(session.messages, key=lambda m: m.created_at)
    
    return ChatSessionDetailOut(
        session=ChatSessionOut(
            session_id=session.session_id,
            user_identifier=session.user_identifier,
            status=session.status,
            tags=session.tags,
            admin_notes=session.admin_notes,
            created_at=session.created_at.isoformat() if session.created_at else None,
            last_message_at=session.last_message_at.isoformat() if session.last_message_at else None,
            updated_at=session.updated_at.isoformat() if session.updated_at else None,
        ),
        messages=[
            ChatMessageOut(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at.isoformat() if msg.created_at else None,
                meta=msg.meta,
            )
            for msg in messages
        ],
    )


class ChatStatsResponse(BaseModel):
    """Respuesta con métricas agregadas de chat sessions."""
    total_sessions: int
    sessions_by_status: dict[str, int]
    total_messages: int
    sessions_with_notes: int
    oldest_session: Optional[datetime]
    newest_session: Optional[datetime]
    avg_messages_per_session: float
    sessions_last_7_days: int
    sessions_last_30_days: int


@router.get("/stats", response_model=ChatStatsResponse)
async def get_chat_stats(
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    """
    Retorna métricas agregadas de sesiones de chat.
    
    **Requiere rol**: admin o colaborador
    """
    from datetime import timedelta
    
    now = datetime.utcnow()
    date_7_days_ago = now - timedelta(days=7)
    date_30_days_ago = now - timedelta(days=30)
    
    # Total de sesiones
    total_sessions_result = await db.execute(select(func.count()).select_from(ChatSession))
    total_sessions = total_sessions_result.scalar() or 0
    
    # Sesiones por status
    status_counts_result = await db.execute(
        select(ChatSession.status, func.count(ChatSession.session_id))
        .group_by(ChatSession.status)
    )
    sessions_by_status = {row[0]: row[1] for row in status_counts_result.all()}
    # Asegurar que todos los status existan en el dict
    for status in ["new", "reviewed", "archived"]:
        if status not in sessions_by_status:
            sessions_by_status[status] = 0
    
    # Total de mensajes
    from db.models import ChatMessage
    total_messages_result = await db.execute(select(func.count()).select_from(ChatMessage))
    total_messages = total_messages_result.scalar() or 0
    
    # Sesiones con notas
    sessions_with_notes_result = await db.execute(
        select(func.count())
        .select_from(ChatSession)
        .where(ChatSession.admin_notes.isnot(None), ChatSession.admin_notes != "")
    )
    sessions_with_notes = sessions_with_notes_result.scalar() or 0
    
    # Fecha más antigua y más reciente
    oldest_result = await db.execute(
        select(func.min(ChatSession.created_at)).select_from(ChatSession)
    )
    oldest_session = oldest_result.scalar()
    
    newest_result = await db.execute(
        select(func.max(ChatSession.created_at)).select_from(ChatSession)
    )
    newest_session = newest_result.scalar()
    
    # Promedio de mensajes por sesión
    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0.0
    
    # Sesiones en los últimos 7 días
    sessions_7d_result = await db.execute(
        select(func.count())
        .select_from(ChatSession)
        .where(ChatSession.created_at >= date_7_days_ago)
    )
    sessions_last_7_days = sessions_7d_result.scalar() or 0
    
    # Sesiones en los últimos 30 días
    sessions_30d_result = await db.execute(
        select(func.count())
        .select_from(ChatSession)
        .where(ChatSession.created_at >= date_30_days_ago)
    )
    sessions_last_30_days = sessions_30d_result.scalar() or 0
    
    return ChatStatsResponse(
        total_sessions=total_sessions,
        sessions_by_status=sessions_by_status,
        total_messages=total_messages,
        sessions_with_notes=sessions_with_notes,
        oldest_session=oldest_session,
        newest_session=newest_session,
        avg_messages_per_session=round(avg_messages, 2),
        sessions_last_7_days=sessions_last_7_days,
        sessions_last_30_days=sessions_last_30_days,
    )


@router.patch("/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
    session_id: str,
    update_data: ChatSessionUpdate,
    _session: SessionData = Depends(require_roles("admin", "colaborador")),
    db: AsyncSession = Depends(get_session),
):
    """
    Actualiza el estado, notas o tags de una sesión de chat.
    
    **Requiere rol**: admin o colaborador
    """
    # Buscar sesión
    stmt = select(ChatSession).where(ChatSession.session_id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")
    
    # Validar status
    if update_data.status and update_data.status not in ("new", "reviewed", "archived"):
        raise HTTPException(status_code=400, detail="Status inválido. Debe ser: new, reviewed, o archived")
    
    # Actualizar campos
    if update_data.status is not None:
        session.status = update_data.status
    if update_data.admin_notes is not None:
        session.admin_notes = update_data.admin_notes
    if update_data.tags is not None:
        session.tags = update_data.tags
    
    await db.commit()
    await db.refresh(session)
    
    return ChatSessionOut(
        session_id=session.session_id,
        user_identifier=session.user_identifier,
        status=session.status,
        tags=session.tags,
        admin_notes=session.admin_notes,
        created_at=session.created_at.isoformat() if session.created_at else None,
        last_message_at=session.last_message_at.isoformat() if session.last_message_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
    )

