// NG-HEADER: Nombre de archivo: purchases.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/purchases.ts
// NG-HEADER: Descripción: Contratos HTTP del módulo Vue de compras.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'

export interface PurchaseLine {
  id: number
  product_id?: number | null
  supplier_sku?: string | null
  title: string
  qty: number
  unit_cost: number
  line_discount: number
  state: 'OK' | 'SIN_VINCULAR' | 'PENDIENTE_CREACION'
}

export interface Purchase {
  id: number
  supplier_id: number
  supplier_name?: string | null
  remito_number: string
  remito_date: string
  status: string
  documented_total?: number | null
  currency?: string
  totals?: { subtotal: number; iva: number; total: number }
  lines: PurchaseLine[]
  attachments?: Array<{ id: number; original_name?: string; filename: string; url: string; sha256?: string }>
}

export interface PurchaseValidationError {
  line_id: number
  errors: string[]
}

export interface PurchaseValidationWarning {
  line_id: number
  code: string
  message: string
}

export interface PurchaseValidationResult {
  status: 'ok'
  unmatched: number
  lines: number
  linked: number
  missing_skus: string[]
  errors: PurchaseValidationError[]
  warnings: PurchaseValidationWarning[]
}

export async function listPurchases(params: Record<string, unknown> = {}) {
  return (await http.get('/purchases', { params })).data as { items: Purchase[]; total: number }
}

export async function getPurchase(id: number) {
  return (await http.get(`/purchases/${id}`)).data as Purchase
}

export async function updatePurchase(id: number, payload: Record<string, unknown>) {
  return (await http.put(`/purchases/${id}`, payload)).data
}

export async function validatePurchase(id: number) {
  return (await http.post(`/purchases/${id}/validate`, {})).data as PurchaseValidationResult
}

export async function confirmPurchase(id: number) {
  return (await http.post(`/purchases/${id}/confirm`, {})).data
}

export async function getPurchaseImpact(id: number) {
  return (await http.get(`/purchases/${id}/impact`)).data
}

export async function importSantaPlanta(supplierId: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  return (await http.post('/purchases/import/santaplanta', body, { params: { supplier_id: supplierId } })).data
}

export async function createPurchase(payload: Record<string, unknown>) {
  return (await http.post('/purchases', payload)).data as { id: number; status: string }
}
