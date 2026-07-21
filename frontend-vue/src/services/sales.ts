// NG-HEADER: Nombre de archivo: sales.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/sales.ts
// NG-HEADER: Descripción: Cliente HTTP tipado del módulo Vue de Ventas y POS.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'

export interface SaleLine { id?: number; product_id: number; product_name?: string; sku?: string; qty: number; unit_price: number; line_discount?: number; total?: number }
export interface Sale {
  id: number; status: string; sale_date: string; sale_kind: string; customer_id?: number; customer_name?: string
  channel_id?: number; channel_name?: string; payment_status?: string; subtotal?: number; discount_amount?: number
  additional_cost_total?: number; tax?: number; total: number; paid_total: number; balance?: number
  lines?: SaleLine[]; payments?: any[]; attachments?: any[]; returns?: any[]; reservations?: any[]; allowed_actions?: Record<string, boolean>
}
export interface SaleDraft {
  customer?: { id?: number; name?: string }; items: SaleLine[]; sale_kind?: string; channel_id?: number
  note?: string; sale_date?: string; additional_costs?: Array<{ concept: string; amount: number }>
  discount_percent?: number; discount_amount?: number
}

export async function listSales(params: Record<string, unknown> = {}) { return (await http.get('/sales', { params })).data }
export async function getSale(id: number) { return (await http.get<Sale>(`/sales/${id}`)).data }
export async function quoteSale(payload: SaleDraft) { return (await http.post('/sales/quote', payload)).data }
export async function createSale(payload: SaleDraft, key: string) { return (await http.post('/sales', payload, { headers: { 'Idempotency-Key': key } })).data }
export async function updateSale(id: number, payload: Record<string, unknown>) { return (await http.patch(`/sales/${id}`, payload)).data }
export async function updateSaleLines(id: number, ops: unknown[]) { return (await http.post(`/sales/${id}/lines`, { ops })).data }
export async function confirmSale(id: number) { return (await http.post(`/sales/${id}/confirm`)).data }
export async function deliverSale(id: number) { return (await http.post(`/sales/${id}/deliver`)).data }
export async function annulSale(id: number, reason: string) { return (await http.post(`/sales/${id}/annul`, null, { params: { reason } })).data }
export async function addPayment(id: number, payload: Record<string, unknown>) { return (await http.post(`/sales/${id}/payments`, payload)).data }
export async function createReturn(id: number, payload: Record<string, unknown>) { return (await http.post(`/sales/${id}/returns`, payload)).data }
export async function reserveSale(id: number) { return (await http.post(`/sales/${id}/reserve`)).data }
export async function releaseReservation(id: number) { return (await http.post(`/sales/${id}/release-reservation`)).data }
export async function listChannels() { return (await http.get('/sales/channels')).data.items }
export async function searchProducts(q: string) { return (await http.get('/sales/catalog/search', { params: { q } })).data.items }
export async function uploadAttachment(id: number, file: File) { const data = new FormData(); data.append('file', file); return (await http.post(`/sales/${id}/attachments`, data)).data }
export async function deleteAttachment(id: number, attachmentId: number) { return (await http.delete(`/sales/${id}/attachments/${attachmentId}`)).data }
export async function getTimeline(id: number) { return (await http.get(`/sales/${id}/timeline`)).data.events }
export async function getMarginReport() { return (await http.get('/sales/reports/margin')).data }
export async function getChannelsReport() { return (await http.get('/sales/reports/channels')).data }
