// NG-HEADER: Nombre de archivo: chats.ts
// NG-HEADER: Ubicación: frontend/src/services/chats.ts
// NG-HEADER: Descripción: Servicio HTTP para gestión de sesiones de chat (Admin)
// NG-HEADER: Lineamientos: Ver AGENTS.md

import http from './http'

export interface ChatSession {
  session_id: string
  user_identifier: string
  status: 'new' | 'reviewed' | 'archived'
  tags?: Record<string, any>
  admin_notes?: string
  created_at: string
  last_message_at?: string
  updated_at: string
  message_count?: number  // Solo en lista
}

export interface ChatMessage {
  id: number
  role: string
  content: string
  created_at: string
  meta?: Record<string, any>
}

export interface ChatSessionDetail {
  session: ChatSession
  messages: ChatMessage[]
}

export interface ChatSessionsListResponse {
  items: ChatSession[]
  total: number
  page: number
  page_size: number
}

export interface ChatSessionUpdate {
  status?: 'new' | 'reviewed' | 'archived'
  admin_notes?: string
  tags?: Record<string, any>
}

export interface ListChatSessionsParams {
  page?: number
  page_size?: number
  status?: string
}

/**
 * Lista sesiones de chat con paginación y filtros
 */
export async function listChatSessions(params: ListChatSessionsParams = {}): Promise<ChatSessionsListResponse> {
  const { page = 1, page_size = 20, status } = params
  const queryParams = new URLSearchParams()
  queryParams.set('page', page.toString())
  queryParams.set('page_size', page_size.toString())
  if (status) {
    queryParams.set('status', status)
  }
  
  const response = await http.get<ChatSessionsListResponse>(`/admin/chats?${queryParams.toString()}`)
  return response.data
}

/**
 * Obtiene el detalle completo de una sesión incluyendo todos sus mensajes
 */
export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  const response = await http.get<ChatSessionDetail>(`/admin/chats/${encodeURIComponent(sessionId)}`)
  return response.data
}

/**
 * Actualiza el estado, notas o tags de una sesión de chat
 */
export async function updateChatSession(sessionId: string, data: ChatSessionUpdate): Promise<ChatSession> {
  const response = await http.patch<ChatSession>(`/admin/chats/${encodeURIComponent(sessionId)}`, data)
  return response.data
}

export interface ChatStats {
  total_sessions: number
  sessions_by_status: Record<string, number>
  total_messages: number
  sessions_with_notes: number
  oldest_session: string | null
  newest_session: string | null
  avg_messages_per_session: number
  sessions_last_7_days: number
  sessions_last_30_days: number
}

/**
 * Obtiene estadísticas agregadas de chat
 */
export async function getChatStats(): Promise<ChatStats> {
  const response = await http.get<ChatStats>('/admin/chats/stats')
  return response.data
}

