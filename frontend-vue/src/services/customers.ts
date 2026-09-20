// NG-HEADER: Nombre de archivo: customers.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/customers.ts
// NG-HEADER: Descripción: Cliente HTTP tipado del módulo Vue de Clientes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'

export interface Customer {
  id: number
  name: string
  email?: string | null
  phone?: string | null
  document_type?: string | null
  document_number?: string | null
  address?: string | null
  city?: string | null
  province?: string | null
  kind?: string | null
  notes?: string | null
  is_active: boolean
  credit_limit?: number | null
  total_compras_bruto?: number
  metrics?: Record<string, number | string | null>
}

export interface CustomerList { items: Customer[]; total: number; page: number; pages: number }

export async function listCustomers(params: Record<string, unknown> = {}, signal?: AbortSignal) {
  return (await http.get<CustomerList>('/customers', { params, signal })).data
}
export async function searchCustomers(q: string, signal?: AbortSignal) {
  return (await http.get<{ items: Customer[] }>('/customers/search', { params: { q }, signal })).data.items
}
export async function getCustomer(id: number) { return (await http.get<Customer>(`/customers/${id}`)).data }
export async function createCustomer(payload: Partial<Customer>) { return (await http.post<{ id: number }>('/customers', payload)).data }
export async function updateCustomer(id: number, payload: Partial<Customer>) { return (await http.patch(`/customers/${id}`, payload)).data }
export async function deactivateCustomer(id: number) { return (await http.delete(`/customers/${id}`)).data }
export async function reactivateCustomer(id: number) { return (await http.post(`/customers/${id}/reactivate`)).data }
export async function getCustomerSales(id: number, page = 1) {
  return (await http.get(`/customers/${id}/sales`, { params: { page, page_size: 10 } })).data
}
export async function getCustomerAccount(id: number, page = 1) {
  return (await http.get(`/customers/${id}/account`, { params: { page, page_size: 20 } })).data
}
