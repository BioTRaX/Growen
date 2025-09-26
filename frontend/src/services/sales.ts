// NG-HEADER: Nombre de archivo: sales.ts
// NG-HEADER: Ubicación: frontend/src/services/sales.ts
// NG-HEADER: Descripción: Servicios HTTP para clientes y ventas
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type Customer = {
  id?: number
  name: string
  email?: string | null
  phone?: string | null
  doc_id?: string | null
  address?: string | null
  notes?: string | null
}

export type SaleItem = {
  product_id: number
  qty: number
  unit_price?: number
  line_discount?: number
}

export type Payment = {
  method: 'efectivo' | 'debito' | 'credito' | 'transferencia' | 'mercadopago' | 'otro'
  amount: number
  reference?: string
}

export async function listCustomers(params?: { q?: string; page?: number; page_size?: number }) {
  const r = await http.get('/sales/customers', { params })
  return r.data as { items: Customer[]; total: number; page: number; pages: number }
}

export async function createCustomer(payload: Customer) {
  const r = await http.post('/sales/customers', payload)
  return r.data as { id: number }
}

export async function updateCustomer(id: number, payload: Partial<Customer>) {
  const r = await http.put(`/sales/customers/${id}`, payload)
  return r.data as { status: 'ok' }
}

export async function deleteCustomer(id: number) {
  const r = await http.delete(`/sales/customers/${id}`)
  return r.data as { status: 'ok'; already?: boolean }
}

export async function createSale(payload: { customer: Partial<Customer>; items: SaleItem[]; payments?: Payment[]; note?: string; status?: 'BORRADOR' | 'CONFIRMADA'; sale_date?: string; }) {
  const r = await http.post('/sales', payload)
  return r.data as { sale_id: number; status: string; total: number }
}

export async function uploadSaleAttachment(saleId: number, file: File) {
  const fd = new FormData()
  fd.append('file', file)
  const r = await http.post(`/sales/${saleId}/attachments`, fd)
  return r.data as { attachment_id: number; path: string }
}

export async function listSales(params?: { status?: string; customer_id?: number; dt_from?: string; dt_to?: string; page?: number; page_size?: number }) {
  const r = await http.get('/sales', { params })
  return r.data as { items: Array<{ id: number; status: string; sale_date: string; customer_id?: number; total: number; paid_total: number }>; total: number; page: number; pages: number }
}

export async function getSale(id: number) {
  const r = await http.get(`/sales/${id}`)
  return r.data as { id: number; status: string; sale_date: string; customer_id?: number; total: number; paid_total: number; lines: Array<{ id: number; product_id: number; qty: number; unit_price: number; line_discount: number }>; payments: Array<{ id: number; method: string; amount: number; reference?: string; paid_at?: string | null }> }
}

export async function annulSale(id: number, reason: string) {
  const r = await http.post(`/sales/${id}/annul`, null, { params: { reason } })
  return r.data as { status: string; restored?: any[]; already?: boolean }
}

export async function confirmSale(id: number) {
  const r = await http.post(`/sales/${id}/confirm`, {})
  return r.data as { status: string; already?: boolean }
}

export async function deliverSale(id: number) {
  const r = await http.post(`/sales/${id}/deliver`, {})
  return r.data as { status: string; already?: boolean }
}

export async function listCustomerSales(customerId: number, params?: { page?: number; page_size?: number }) {
  const r = await http.get(`/sales/customers/${customerId}/sales`, { params })
  return r.data as { items: Array<{ id: number; status: string; sale_date: string; total: number; paid_total: number }>; total: number; page: number; pages: number }
}
