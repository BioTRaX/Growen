// NG-HEADER: Nombre de archivo: categories.ts
// NG-HEADER: Ubicación: frontend/src/services/categories.ts
// NG-HEADER: Descripción: Servicios HTTP para categorías.
// NG-HEADER: Lineamientos: Ver AGENTS.md
export interface Category {
  id: number
  name: string
  parent_id: number | null
  path: string
}
import { baseURL as base } from './http'

export async function listCategories(): Promise<Category[]> {
  const res = await fetch(`${base}/categories`, { credentials: 'include' })
  if (!res.ok) throw new Error('Error de red')
  return res.json()
}

export async function createCategory(name: string, parent_id?: number | null): Promise<Category & { parent_id: number | null; path?: string }> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  if (m) headers['X-CSRF-Token'] = decodeURIComponent(m[1])
  const res = await fetch(`${base}/categories`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify({ name, parent_id: parent_id ?? null }),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const data = await res.json(); if (data?.detail) msg = data.detail } catch {}
    throw new Error(msg)
  }
  return res.json()
}
