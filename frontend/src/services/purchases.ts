// NG-HEADER: Nombre de archivo: purchases.ts
// NG-HEADER: Ubicación: frontend/src/services/purchases.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type PurchaseLine = {
  id?: number
  supplier_item_id?: number | null
  product_id?: number | null
  supplier_sku?: string | null
  title: string
  qty: number
  unit_cost: number
  line_discount?: number
  state?: string
  note?: string
  op?: 'upsert' | 'delete'
}

export type Purchase = {
  id: number
  supplier_id: number
  remito_number: string
  remito_date: string
  status: 'BORRADOR' | 'VALIDADA' | 'CONFIRMADA' | 'ANULADA'
  global_discount: number
  vat_rate: number
  depot_id?: number | null
  note?: string | null
  lines?: PurchaseLine[]
}

export async function listPurchases(params?: Record<string, any>) {
  const r = await http.get('/purchases', { params })
  return r.data as { items: Purchase[]; total: number; page: number; pages: number }
}

export async function getPurchase(id: number) {
  const r = await http.get(`/purchases/${id}`)
  return r.data as Purchase
}

export async function getPurchaseLogs(id: number, limit: number = 200) {
  const r = await http.get(`/purchases/${id}/logs`, { params: { limit } })
  return r.data as { items: { action: string; created_at?: string; meta: any }[] }
}

export async function createDraft(payload: Partial<Purchase>) {
  const r = await http.post('/purchases', payload)
  return r.data as { id: number; status: string }
}

export async function updatePurchase(id: number, payload: Partial<Purchase> & { lines?: PurchaseLine[] }) {
  const r = await http.put(`/purchases/${id}`, payload)
  return r.data
}

export async function validatePurchase(id: number) {
  const r = await http.post(`/purchases/${id}/validate`, {})
  return r.data as { status: string; unmatched: number; lines: number }
}

export async function confirmPurchase(id: number, debug: boolean = false) {
  const r = await http.post(`/purchases/${id}/confirm`, {}, { params: { debug: debug ? 1 : 0 } })
  return r.data as { status: string; applied_deltas?: { product_id: number; product_title?: string | null; delta: number; new: number; old: number }[]; unresolved_lines?: number[] }
}

export async function resendPurchaseStock(id: number, apply: boolean, debug: boolean = false) {
  const r = await http.post(`/purchases/${id}/resend-stock`, {}, { params: { apply: apply ? 1 : 0, debug: debug ? 1 : 0 } })
  return r.data as { status: string; mode: 'apply' | 'preview'; applied_deltas?: { product_id: number; product_title?: string | null; delta: number; new: number; old: number }[]; unresolved_lines?: number[] }
}

export async function cancelPurchase(id: number, note: string) {
  const r = await http.post(`/purchases/${id}/cancel`, { note })
  return r.data
}

export async function importSantaPlanta(supplier_id: number, file: File, debug: boolean = false, forceOcr: boolean = false) {
  const fd = new FormData()
  fd.append('file', file)
  const r = await http.post(`/purchases/import/santaplanta`, fd, {
    params: {
      supplier_id,
      debug: debug ? 1 : 0,
      force_ocr: forceOcr ? 1 : 0,
    }
  })
  return r.data as { purchase_id: number; status: string; filename: string; correlation_id?: string; parsed?: any; debug?: any }
}

export function exportUnmatched(id: number, fmt: 'csv' | 'xlsx' = 'csv') {
  window.open(`${http.defaults.baseURL}/purchases/${id}/unmatched/export?fmt=${fmt}`, '_blank')
}

export async function deletePurchase(id: number) {
  const r = await http.delete(`/purchases/${id}`)
  return r.data as { status: string }
}

export async function searchSupplierProducts(supplierId: number, sku: string) {
  const r = await http.get(`/suppliers/${supplierId}/items`, { params: { sku_like: sku } })
  return r.data as { id: number; supplier_product_id: string; title: string; product_id: number }[]
}

