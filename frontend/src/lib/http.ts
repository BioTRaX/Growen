// NG-HEADER: Nombre de archivo: http.ts
// NG-HEADER: Ubicación: frontend/src/lib/http.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
export type ChatResponse = { role: string; text: string }

export async function chatHttp(text: string): Promise<ChatResponse> {
  const { baseURL: base } = await import('../services/http') as any
  const res = await fetch(`${base}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // Enviamos credenciales para mantener la sesión del usuario.
    credentials: 'include',
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
