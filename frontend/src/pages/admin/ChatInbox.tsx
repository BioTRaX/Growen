// NG-HEADER: Nombre de archivo: ChatInbox.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/ChatInbox.tsx
// NG-HEADER: Descripción: Dashboard de administración de conversaciones de chat (Inbox)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import { listChatSessions, getChatSession, updateChatSession, type ChatSession, type ChatSessionDetail, type ChatMessage } from '../../services/chats'
import { useToast } from '../../components/ToastProvider'

export default function ChatInbox() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [selectedSession, setSelectedSession] = useState<ChatSessionDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [adminNotes, setAdminNotes] = useState('')
  const { push } = useToast()

  const pageSize = 20

  async function loadSessions() {
    setLoading(true)
    try {
      const response = await listChatSessions({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
      })
      setSessions(response.items)
      setTotal(response.total)
    } catch (error: any) {
      push({ kind: 'error', title: 'Error', message: error?.response?.data?.detail || 'Error cargando sesiones' })
    } finally {
      setLoading(false)
    }
  }

  async function loadSessionDetail(sessionId: string) {
    try {
      const detail = await getChatSession(sessionId)
      setSelectedSession(detail)
      setAdminNotes(detail.session.admin_notes || '')
    } catch (error: any) {
      push({ kind: 'error', title: 'Error', message: error?.response?.data?.detail || 'Error cargando sesión' })
    }
  }

  async function handleSelectSession(session: ChatSession) {
    setSelectedSession(null)
    await loadSessionDetail(session.session_id)
  }

  async function handleUpdateStatus(newStatus: string) {
    if (!selectedSession) return
    setSaving(true)
    try {
      await updateChatSession(selectedSession.session.session_id, { status: newStatus as any })
      await loadSessionDetail(selectedSession.session.session_id)
      await loadSessions()
      push({ kind: 'success', title: 'Actualizado', message: 'Estado de sesión actualizado' })
    } catch (error: any) {
      push({ kind: 'error', title: 'Error', message: error?.response?.data?.detail || 'Error actualizando estado' })
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveNotes() {
    if (!selectedSession) return
    setSaving(true)
    try {
      await updateChatSession(selectedSession.session.session_id, { admin_notes: adminNotes })
      await loadSessionDetail(selectedSession.session.session_id)
      push({ kind: 'success', title: 'Guardado', message: 'Notas guardadas' })
    } catch (error: any) {
      push({ kind: 'error', title: 'Error', message: error?.response?.data?.detail || 'Error guardando notas' })
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    loadSessions()
  }, [page, statusFilter])

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getPreviewText = (session: ChatSession) => {
    // El preview se mostrará cuando tengamos acceso al último mensaje
    // Por ahora, mostramos el user_identifier
    return session.user_identifier
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      new: 'var(--primary)',
      reviewed: 'var(--success)',
      archived: 'var(--muted)',
    }
    const labels: Record<string, string> = {
      new: 'Nuevo',
      reviewed: 'Revisado',
      archived: 'Archivado',
    }
    return (
      <span
        style={{
          fontSize: 11,
          padding: '2px 6px',
          borderRadius: 4,
          background: colors[status] || 'var(--muted)',
          color: 'white',
        }}
      >
        {labels[status] || status}
      </span>
    )
  }

  return (
    <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 200px)', minHeight: 600 }}>
      {/* Columna izquierda: Lista de conversaciones */}
      <div style={{ width: '40%', display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)' }}>
        <div style={{ padding: 12, borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ margin: 0, marginBottom: 8 }}>Conversaciones</h3>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <select
              className="select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              style={{ flex: 1 }}
            >
              <option value="">Todos</option>
              <option value="new">Nuevos</option>
              <option value="reviewed">Revisados</option>
              <option value="archived">Archivados</option>
            </select>
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            Total: {total} sesiones
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            <div style={{ padding: 12, textAlign: 'center', color: 'var(--muted)' }}>Cargando...</div>
          ) : sessions.length === 0 ? (
            <div style={{ padding: 12, textAlign: 'center', color: 'var(--muted)' }}>No hay conversaciones</div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                onClick={() => handleSelectSession(session)}
                style={{
                  padding: 12,
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                  background: selectedSession?.session.session_id === session.session_id ? 'var(--bg-hover)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (selectedSession?.session.session_id !== session.session_id) {
                    e.currentTarget.style.background = 'var(--bg-hover)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedSession?.session.session_id !== session.session_id) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <div style={{ fontWeight: 'bold', fontSize: 14 }}>
                    {session.status === 'new' && (
                      <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--primary)', marginRight: 6 }} />
                    )}
                    {session.user_identifier}
                  </div>
                  {getStatusBadge(session.status)}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
                  {session.last_message_at ? formatDate(session.last_message_at) : formatDate(session.created_at)}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text)' }}>
                  {session.message_count || 0} mensajes
                </div>
              </div>
            ))
          )}
        </div>

        {/* Paginación */}
        <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            className="btn"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
          >
            Anterior
          </button>
          <span style={{ fontSize: 12 }}>
            Página {page} de {Math.ceil(total / pageSize)}
          </span>
          <button
            className="btn"
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(total / pageSize) || loading}
          >
            Siguiente
          </button>
        </div>
      </div>

      {/* Columna derecha: Vista de chat */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {selectedSession ? (
          <>
            {/* Header de sesión */}
            <div style={{ padding: 12, borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div>
                  <h3 style={{ margin: 0 }}>{selectedSession.session.user_identifier}</h3>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    Creada: {formatDate(selectedSession.session.created_at)}
                    {selectedSession.session.last_message_at && ` • Último mensaje: ${formatDate(selectedSession.session.last_message_at)}`}
                  </div>
                </div>
                {getStatusBadge(selectedSession.session.status)}
              </div>
            </div>

            {/* Mensajes */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 12, background: 'var(--bg)' }}>
              {selectedSession.messages.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 24 }}>
                  No hay mensajes en esta conversación
                </div>
              ) : (
                selectedSession.messages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      marginBottom: 16,
                      display: 'flex',
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '70%',
                        padding: '8px 12px',
                        borderRadius: 12,
                        background: msg.role === 'user' ? 'var(--primary)' : 'var(--bg-hover)',
                        color: msg.role === 'user' ? 'white' : 'var(--text)',
                      }}
                    >
                      <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 4 }}>
                        {msg.role === 'user' ? 'Usuario' : 'Asistente'} • {formatDate(msg.created_at)}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Panel de acciones */}
            <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 12, fontWeight: 'bold' }}>
                  Estado:
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {(['new', 'reviewed', 'archived'] as const).map((status) => (
                    <button
                      key={status}
                      className="btn"
                      onClick={() => handleUpdateStatus(status)}
                      disabled={saving || selectedSession.session.status === status}
                      style={{
                        opacity: selectedSession.session.status === status ? 0.6 : 1,
                      }}
                    >
                      {status === 'new' ? 'Nuevo' : status === 'reviewed' ? 'Revisado' : 'Archivado'}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', marginBottom: 4, fontSize: 12, fontWeight: 'bold' }}>
                  Notas administrativas:
                </label>
                <textarea
                  className="input"
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  placeholder="Notas para esta conversación..."
                  rows={3}
                  style={{ width: '100%', resize: 'vertical' }}
                />
                <button
                  className="btn"
                  onClick={handleSaveNotes}
                  disabled={saving}
                  style={{ marginTop: 8 }}
                >
                  {saving ? 'Guardando...' : 'Guardar notas'}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
            Selecciona una conversación para ver los detalles
          </div>
        )}
      </div>
    </div>
  )
}

