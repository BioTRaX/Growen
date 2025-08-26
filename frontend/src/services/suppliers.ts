export interface Supplier {
  id: number
  name: string
  slug: string
}
import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function listSuppliers(): Promise<Supplier[]> {
  const r = await fetch(`${base}/suppliers`, {
    credentials: 'include',
    headers: csrfHeaders(),
  })
  if (!r.ok) throw new Error('Error de red')
  return r.json()
}

export async function createSupplier(payload: { name: string; slug: string }): Promise<Supplier> {
  const headers = { ...csrfHeaders(), 'Content-Type': 'application/json' }
  const r = await fetch(`${base}/suppliers`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify(payload),
  })
  if (r.status === 409) throw new Error('slug existente')
  if (!r.ok) throw new Error('datos inválidos')
  return r.json()
}
