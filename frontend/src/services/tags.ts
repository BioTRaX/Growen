// NG-HEADER: Nombre de archivo: tags.ts
// NG-HEADER: Ubicación: frontend/src/services/tags.ts
// NG-HEADER: Descripción: Servicios para gestión de tags y asignación a productos
// NG-HEADER: Lineamientos: Ver AGENTS.md

export interface Tag {
  id: number
  name: string
}

import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function listTags(q?: string): Promise<Tag[]> {
  const url = new URL(base + '/tags', window.location.origin)
  if (q) url.searchParams.set('q', q)
  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: csrfHeaders(),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createTag(name: string): Promise<Tag> {
  const headers = {
    ...csrfHeaders(),
    'Content-Type': 'application/json',
  }
  const res = await fetch(`${base}/tags`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data?.detail) msg = data.detail
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export async function assignTagsToProduct(productId: number, tagNames: string[]): Promise<{
  product_id: number
  assigned_tags: string[]
  new_assignments: string[]
}> {
  const headers = {
    ...csrfHeaders(),
    'Content-Type': 'application/json',
  }
  const res = await fetch(`${base}/tags/products/${productId}/tags`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ tag_names: tagNames }),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data?.detail) msg = data.detail
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export async function removeTagFromProduct(productId: number, tagId: number): Promise<{
  product_id: number
  tag_id: number
  removed: boolean
}> {
  const headers = {
    ...csrfHeaders(),
  }
  const res = await fetch(`${base}/tags/products/${productId}/tags/${tagId}`, {
    method: 'DELETE',
    headers,
    credentials: 'include',
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data?.detail) msg = data.detail
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export async function bulkAssignTags(productIds: number[], tagNames: string[]): Promise<{
  product_ids: number[]
  tag_names: string[]
  tags_assigned: number
  new_relations_created: number
  existing_relations_skipped: number
}> {
  const headers = {
    ...csrfHeaders(),
    'Content-Type': 'application/json',
  }
  const res = await fetch(`${base}/tags/products/bulk-tags`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ product_ids: productIds, tag_names: tagNames }),
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      if (data?.detail) msg = data.detail
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

