// NG-HEADER: Nombre de archivo: bugReport.ts
// NG-HEADER: Ubicación: frontend/src/services/bugReport.ts
// NG-HEADER: Descripción: Cliente HTTP para enviar reportes de bug al backend
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type BugReportPayload = {
  message: string
  url?: string
  user_agent?: string
  stack?: string
  cid?: string
  context?: Record<string, any>
  screenshot?: string
}

export async function sendBugReport(payload: BugReportPayload): Promise<{status: string; id?: string} | null> {
  try {
    const { data } = await http.post('/bug-report', payload, { timeout: 8000 })
    return data
  } catch {
    return null
  }
}
