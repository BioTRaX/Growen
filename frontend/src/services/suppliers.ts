// NG-HEADER: Nombre de archivo: suppliers.ts
// NG-HEADER: Ubicación: frontend/src/services/suppliers.ts
// NG-HEADER: Descripción: Servicios para CRUD de proveedores y archivos asociados
// NG-HEADER: Lineamientos: Ver AGENTS.md
export interface Supplier {
  id: number
  name: string
  slug: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
  extra_json?: any
  created_at?: string
}
import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function listSuppliers(): Promise<{ id: number; slug: string; name: string; created_at: string; last_upload_at?: string | null; files_count: number }[]> {
  const r = await fetch(`${base}/suppliers`, { credentials: 'include', headers: csrfHeaders() })
  if (!r.ok) throw new Error('Error de red')
  return r.json()
}

// ------------ Supplier CRUD ------------

type SupplierCreatePayload = {
  slug: string
  name: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
  extra_json?: any
}

export async function createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
  const headers = { ...csrfHeaders(), 'Content-Type': 'application/json' }
  const norm = { ...payload, slug: payload.slug.trim().toLowerCase() }
  const r = await fetch(`${base}/suppliers`, { method: 'POST', credentials: 'include', headers, body: JSON.stringify(norm) })
  if (r.status === 409) throw new Error('slug existente')
  if (r.status === 415) throw new Error('content-type inválido')
  if (r.status === 400) {
    try { const j = await r.json(); throw new Error(j.message || 'payload inválido') } catch { throw new Error('payload inválido') }
  }
  if (!r.ok) throw new Error('error inesperado')
  return r.json()
}

export async function getSupplier(id: number): Promise<Supplier> {
  const r = await fetch(`${base}/suppliers/${id}`, { credentials: 'include', headers: csrfHeaders() })
  if (r.status === 404) throw new Error('no encontrado')
  if (!r.ok) throw new Error('error')
  return r.json()
}

export async function updateSupplier(id: number, payload: SupplierCreatePayload): Promise<Supplier> {
  const headers = { ...csrfHeaders(), 'Content-Type': 'application/json' }
  const r = await fetch(`${base}/suppliers/${id}`, { method: 'PATCH', credentials: 'include', headers, body: JSON.stringify(payload) })
  if (r.status === 404) throw new Error('no encontrado')
  if (!r.ok) throw new Error('error actualización')
  return r.json()
}

// ------------ Supplier Items ------------

export interface SupplierItem {
  id: number
  supplier_product_id: string
  title: string
  product_id?: number | null
  purchase_price?: number | null
  sale_price?: number | null
}

type SupplierItemCreatePayload = {
  supplier_product_id: string
  title: string
  product_id?: number | null
  purchase_price?: number | null
  sale_price?: number | null
}

export async function createSupplierItem(supplierId: number, payload: SupplierItemCreatePayload): Promise<SupplierItem> {
  const headers = { ...csrfHeaders(), 'Content-Type': 'application/json' }
  const r = await fetch(`${base}/suppliers/${supplierId}/items`, { method: 'POST', credentials: 'include', headers, body: JSON.stringify(payload) })
  if (r.status === 409) {
    const j = await r.json().catch(() => null)
    throw new Error(j?.message || 'item duplicado')
  }
  if (r.status === 400) throw new Error('payload inválido')
  if (r.status === 404) throw new Error('proveedor no encontrado')
  if (!r.ok) throw new Error('error creación')
  return r.json()
}

// ------------ Supplier Files ------------

export interface SupplierFileMeta {
  id: number
  filename: string
  original_name: string
  uploaded_at: string
  sha256: string
  size_bytes?: number
  content_type?: string | null
  processed: boolean
  dry_run: boolean
  rows: number
  duplicate?: boolean
}

export async function listSupplierFiles(supplierId: number): Promise<SupplierFileMeta[]> {
  const r = await fetch(`${base}/suppliers/${supplierId}/files`, { credentials: 'include', headers: csrfHeaders() })
  if (!r.ok) throw new Error('error listando archivos')
  return r.json()
}

export async function uploadSupplierFile(supplierId: number, file: File, notes?: string): Promise<SupplierFileMeta> {
  const fd = new FormData()
  fd.append('file', file)
  if (notes) fd.append('notes', notes)
  const r = await fetch(`${base}/suppliers/${supplierId}/files/upload`, {
    method: 'POST',
    credentials: 'include',
    headers: { ...csrfHeaders() },
    body: fd
  })
  if (r.status === 400) throw new Error('tipo de archivo no permitido')
  if (r.status === 413) throw new Error('archivo demasiado grande')
  if (r.status === 404) throw new Error('proveedor no encontrado')
  if (!r.ok) throw new Error('error subida')
  return r.json()
}

export function downloadSupplierFile(fileId: number) {
  const url = `${base}/suppliers/files/${fileId}/download`
  // Abrir en nueva pestaña para descarga directa
  window.open(url, '_blank')
}

// ------------ Supplier Search (Autocomplete) ------------

export interface SupplierSearchItem {
  id: number
  name: string
  slug: string
}

export async function searchSuppliers(q: string, limit = 20): Promise<SupplierSearchItem[]> {
  const qp = new URLSearchParams({ q: q || '', limit: String(limit) })
  const r = await fetch(`${base}/suppliers/search?${qp.toString()}`, { credentials: 'include' })
  if (!r.ok) throw new Error('error de red')
  const data = await r.json()
  if (!Array.isArray(data)) return []
  return data
}
