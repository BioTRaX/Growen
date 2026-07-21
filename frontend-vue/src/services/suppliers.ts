// NG-HEADER: Nombre de archivo: suppliers.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/suppliers.ts
// NG-HEADER: Descripción: Contratos HTTP para búsqueda y alta de proveedores.
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

export interface SupplierCreatePayload {
  slug: string
  name: string
  location?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
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
