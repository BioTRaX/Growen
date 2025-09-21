// NG-HEADER: Nombre de archivo: backups.ts
// NG-HEADER: Ubicación: frontend/src/services/backups.ts
// NG-HEADER: Descripción: Cliente HTTP para endpoints de backups (admin)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type BackupItem = {
  filename: string
  size: number
  modified: string
}

export async function listBackups(): Promise<BackupItem[]> {
  const r = await http.get('/admin/backups')
  return (r.data?.items || []) as BackupItem[]
}

export async function runBackup(): Promise<{ file: string }> {
  const r = await http.post('/admin/backups/run')
  return { file: r.data?.meta?.file }
}

export function downloadBackup(filename: string) {
  const url = `/admin/backups/download/${encodeURIComponent(filename)}`
  window.location.href = url
}
