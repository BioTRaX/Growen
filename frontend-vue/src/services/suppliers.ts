// NG-HEADER: Nombre de archivo: suppliers.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/suppliers.ts
// NG-HEADER: Descripción: Contratos HTTP para búsqueda, alta, detalle, edición y archivos de proveedores.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'

export interface SupplierSummary {
  id: number
  slug: string
  name: string
  created_at?: string
  last_upload_at?: string | null
  files_count?: number
}

export interface Supplier {
  id: number
  slug: string
  name: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
  extra_json?: Record<string, unknown> | null
  created_at?: string
}

export interface SupplierCreatePayload {
  slug: string
  name: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
  extra_json?: Record<string, unknown> | null
}

export interface SupplierUpdatePayload {
  name: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
  extra_json?: Record<string, unknown> | null
}

export interface SupplierFileMeta {
  id: number
  filename: string
  original_name: string
  uploaded_at: string
  sha256: string
  size_bytes?: number | null
  content_type?: string | null
  processed: boolean
  dry_run: boolean
  rows: number
  duplicate?: boolean
}

export async function searchSuppliers(q = '', limit = 30): Promise<SupplierSummary[]> {
  return (await http.get('/suppliers/search', { params: { q, limit } })).data
}

export async function listSuppliers(): Promise<SupplierSummary[]> {
  return (await http.get('/suppliers')).data
}

export async function createSupplier(payload: SupplierCreatePayload): Promise<SupplierSummary> {
  return (await http.post('/suppliers', payload)).data
}

export async function getSupplier(id: number): Promise<Supplier> {
  return (await http.get(`/suppliers/${id}`)).data
}

export async function updateSupplier(id: number, payload: SupplierUpdatePayload): Promise<Supplier> {
  return (await http.patch(`/suppliers/${id}`, payload)).data
}

export async function listSupplierFiles(supplierId: number): Promise<SupplierFileMeta[]> {
  return (await http.get(`/suppliers/${supplierId}/files`)).data
}

export async function uploadSupplierFile(supplierId: number, file: File, notes?: string): Promise<SupplierFileMeta> {
  const formData = new FormData()
  formData.append('file', file)
  if (notes) formData.append('notes', notes)
  return (await http.post(`/suppliers/${supplierId}/files/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })).data
}

export async function bulkDeleteSuppliers(ids: number[]): Promise<{
  requested: number[]
  deleted: number[]
  blocked: { id: number; reasons: string[]; counts?: Record<string, number> }[]
  not_found: number[]
}> {
  return (await http.delete('/suppliers', { data: { ids } })).data
}
