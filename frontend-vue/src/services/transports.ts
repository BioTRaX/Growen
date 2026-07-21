// NG-HEADER: Nombre de archivo: transports.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/transports.ts
// NG-HEADER: Descripción: Helpers comunes para URLs API, descargas, WebSocket y Server-Sent Events.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { apiBaseUrl, http } from './http'

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  if (/^https?:\/\//.test(apiBaseUrl)) return new URL(`${apiBaseUrl}${cleanPath}`).toString()
  return `${apiBaseUrl}${cleanPath}`
}

export function websocketUrl(path: string): string {
  const url = new URL(apiUrl(path), window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export async function downloadBlob(path: string, filename: string): Promise<void> {
  const response = await http.get<Blob>(path, { responseType: 'blob' })
  const href = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export function openEventStream(path: string): EventSource {
  return new EventSource(apiUrl(path), { withCredentials: true })
}

export function openWebSocket(path: string): WebSocket {
  return new WebSocket(websocketUrl(path))
}
