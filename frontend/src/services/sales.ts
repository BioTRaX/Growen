// NG-HEADER: Nombre de archivo: sales.ts
// NG-HEADER: Ubicación: frontend/src/services/sales.ts
// NG-HEADER: Descripción: Servicios HTTP para ventas (POS y reportes)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'
import type { Customer } from './customers'

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

export type AdditionalCost = {
  concept: string
  amount: number
}

export type SalesChannel = {
  id: number
  name: string
  created_at: string
}

export type CreateSalePayload = {
  customer: Partial<Customer>
  items: SaleItem[]
  payments?: Payment[]
  note?: string
  status?: 'BORRADOR' | 'CONFIRMADA'
  sale_date?: string
  channel_id?: number
  additional_costs?: AdditionalCost[]
}

export async function createSale(payload: CreateSalePayload) {
  const r = await http.post('/sales', payload)
  return r.data as { sale_id: number; status: string; total: number }
}

// --- Canales de Venta ---

export async function listChannels() {
  const r = await http.get('/sales/channels')
  return r.data as { items: SalesChannel[]; total: number }
}

export async function createChannel(name: string) {
  const r = await http.post('/sales/channels', { name })
  return r.data as SalesChannel
}

export async function deleteChannel(id: number) {
  const r = await http.delete(`/sales/channels/${id}`)
  return r.data as { status: string; id: number }
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

export type SaleDetail = {
  id: number
  status: string
  sale_date: string
  customer_id?: number
  channel_id?: number
  additional_costs?: AdditionalCost[]
  total: number
  paid_total: number
  payment_status?: string
  lines: Array<{
    id: number
    product_id: number
    qty: number
    unit_price: number
    line_discount: number
  }>
  payments: Array<{
    id: number
    method: string
    amount: number
    reference?: string
    paid_at?: string | null
  }>
}

export async function getSale(id: number) {
  const r = await http.get(`/sales/${id}`)
  return r.data as SaleDetail
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

