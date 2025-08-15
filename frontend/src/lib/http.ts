export type ChatResponse = { role: string; text: string }

export async function chatHttp(text: string): Promise<ChatResponse> {
  const base = (import.meta.env.VITE_API_BASE as string) || ''
  const res = await fetch(`${base}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
