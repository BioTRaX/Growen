// NG-HEADER: Nombre de archivo: adminCore.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/adminCore.ts
// NG-HEADER: Descripción: Contratos del panel Vue para usuarios y backups administrativos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'
import { downloadBlob } from './transports'

export interface AdminUser { id: number; identifier: string; email?: string | null; name?: string | null; role: string; supplier_id?: number | null }
export interface AdminUserPayload { identifier?: string; email?: string; name?: string; password?: string; role?: string; supplier_id?: number }
export interface BackupItem { filename: string; size: number; modified: string }

export const listUsers = async (q = '', role = '') => (await http.get<AdminUser[]>('/auth/users', { params: { q: q || undefined, role: role || undefined } })).data
export const createUser = async (payload: AdminUserPayload) => (await http.post('/auth/users', payload)).data
export const updateUser = async (id: number, payload: AdminUserPayload) => (await http.patch(`/auth/users/${id}`, payload)).data
export const deleteUser = async (id: number) => (await http.delete(`/auth/users/${id}`)).data
export const resetUserPassword = async (id: number) => (await http.post<{ password: string }>(`/auth/users/${id}/reset-password`)).data
export const listBackups = async () => (await http.get<{ items: BackupItem[] }>('/admin/backups')).data.items ?? []
export const runBackup = async () => (await http.post<{ meta?: { file?: string } }>('/admin/backups/run')).data
export const downloadBackup = async (filename: string) => downloadBlob(`/admin/backups/download/${encodeURIComponent(filename)}`, filename)
