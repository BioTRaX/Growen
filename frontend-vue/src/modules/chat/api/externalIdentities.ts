// NG-HEADER: Nombre de archivo: externalIdentities.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/chat/api/externalIdentities.ts
// NG-HEADER: Descripción: Cliente seguro para vínculos Telegram propios y administrativos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from '../../../services/http'

export interface TelegramLinkingStatus {
  enabled: boolean
  public_bot_enabled: boolean
  transport: 'polling'
  admin_second_approval: boolean
}

export interface ExternalIdentity {
  id: number
  provider: string
  masked_identifier: string
  status: 'active' | 'pending_approval' | 'revoked'
  created_at?: string | null
  last_seen_at?: string | null
  user_id?: number | null
}

export interface LinkRequest {
  code: string
  command: string
  expires_at: string
}

export const getTelegramLinkingStatus = async () =>
  (await http.get<TelegramLinkingStatus>('/auth/external-identities/telegram/status')).data

export const listMyExternalIdentities = async () =>
  (await http.get<ExternalIdentity[]>('/auth/me/external-identities')).data

export const createTelegramLinkRequest = async (password: string) =>
  (await http.post<LinkRequest>('/auth/external-identities/telegram/link-request', { password })).data

export const revokeMyExternalIdentity = async (id: number) =>
  (await http.delete(`/auth/me/external-identities/${id}`)).data

export const listAdminExternalIdentities = async () =>
  (await http.get<ExternalIdentity[]>('/admin/external-identities')).data

export const approveExternalIdentity = async (id: number) =>
  (await http.post(`/admin/external-identities/${id}/approve`)).data

export const revokeAdminExternalIdentity = async (id: number) =>
  (await http.post(`/admin/external-identities/${id}/revoke`)).data
