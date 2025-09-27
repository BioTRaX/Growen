// NG-HEADER: Nombre de archivo: customers.ts
// NG-HEADER: Ubicación: frontend/src/services/customers.ts
// NG-HEADER: Descripción: Servicios HTTP para clientes (CRUD, búsqueda y ventas asociadas)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type Customer = {
  id?: number
  name: string
  email?: string | null
  phone?: string | null
  doc_id?: string | null
  document_type?: string | null
  document_number?: string | null
  address?: string | null
  city?: string | null
  province?: string | null
  notes?: string | null
  kind?: 'cf' | 'ri' | 'minorista' | 'mayorista' | null
  is_active?: boolean
}

export async function listCustomers(params?: {
  q?: string
  page?: number
  page_size?: number
  kind?: string
  only_active?: boolean
}) {
  const r = await http.get('/customers', { params })
  return r.data as { items: Customer[]; total: number; page: number; pages: number }
}

export async function createCustomer(payload: Customer) {
  const r = await http.post('/customers', payload)
  return r.data as { id: number }
}

export async function updateCustomer(id: number, payload: Partial<Customer>) {
  const r = await http.put(`/customers/${id}`, payload)
  return r.data as { status: 'ok' }
}

export async function deleteCustomer(id: number) {
  const r = await http.delete(`/customers/${id}`)
  return r.data as { status: 'ok'; already?: boolean }
}

export async function listCustomerSales(customerId: number, params?: { page?: number; page_size?: number }) {
  const r = await http.get(`/customers/${customerId}/sales`, { params })
  return r.data as {
    items: Array<{ id: number; status: string; sale_date: string; total: number; paid_total: number }>
    total: number
    page: number
    pages: number
  }
}

export async function searchCustomers(query: string, limit = 20) {
  const r = await http.get('/customers/search', { params: { q: query, limit } })
  return r.data as {
    query: string
    items: Array<{
      id: number
      name: string
      email?: string | null
      phone?: string | null
      document_type?: string | null
      document_number?: string | null
      kind?: string | null
      weight: number
    }>
    count: number
  }
}
