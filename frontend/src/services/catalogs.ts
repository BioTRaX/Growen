// NG-HEADER: Nombre de archivo: catalogs.ts
// NG-HEADER: Ubicación: frontend/src/services/catalogs.ts
// NG-HEADER: Descripción: Cliente HTTP para generación y consulta de catálogos PDF.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function generateCatalog(ids: number[]): Promise<void> {
  const res = await fetch(base + '/catalogs/generate', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ ids }),
  })
  if (!res.ok) {
    let detail = 'Error generando catálogo'
    try {
      const j = await res.json(); if (j.detail) detail = j.detail
    } catch {}
    throw new Error(detail)
  }
}

export async function headLatestCatalog(): Promise<boolean> {
  const res = await fetch(base + '/catalogs/latest', {
    method: 'HEAD',
    credentials: 'include',
  })
  return res.ok
}

export async function deleteCatalog(id: string): Promise<void> {
  const res = await fetch(base + `/catalogs/${id}`, { method: 'DELETE', credentials: 'include' })
  if (!res.ok) {
    let detail = 'Error eliminando catálogo'
    try { const j = await res.json(); if (j.detail) detail = j.detail } catch {}
    throw new Error(detail)
  }
}

export interface CatalogListItem {
  id: string
  filename: string
  size: number
  modified_at: string
  latest: boolean
}

export interface CatalogListResponse {
  items: CatalogListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export async function listCatalogs(params: {page?: number; page_size?: number; from_dt?: string; to_dt?: string} = {}): Promise<CatalogListResponse> {
  const q = new URLSearchParams()
  if (params.page) q.set('page', String(params.page))
  if (params.page_size) q.set('page_size', String(params.page_size))
  if (params.from_dt) q.set('from_dt', params.from_dt)
  if (params.to_dt) q.set('to_dt', params.to_dt)
  const url = base + '/catalogs' + (q.toString() ? ('?' + q.toString()) : '')
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) throw new Error('Error listando catálogos')
  return await res.json()
}
