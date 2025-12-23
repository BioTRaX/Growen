// NG-HEADER: Nombre de archivo: purchases.ts
// NG-HEADER: UbicaciÃ³n: frontend/src/services/purchases.ts
// NG-HEADER: Descripción: Servicios HTTP para operaciones de compras.
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
  return r.data as { status: string; unmatched: number; lines: number; linked?: number; missing_skus?: string[] }
}

export async function confirmPurchase(id: number, debug: boolean = false) {
  const r = await http.post(`/purchases/${id}/confirm`, {}, { params: { debug: debug ? 1 : 0 } })
  return r.data as {
    status: string
    applied_deltas?: { product_id: number; product_title?: string | null; line_title?: string | null; supplier_sku?: string | null; delta: number; new: number; old: number }[]
    unresolved_lines?: number[]
    totals?: {
      purchase_total: number
      applied_total: number
      diff: number
      tolerance_abs: number
      tolerance_pct: number
      mismatch: boolean
    }
    can_rollback?: boolean
    hint?: string
  }
}

export async function resendPurchaseStock(id: number, apply: boolean, debug: boolean = false) {
  const r = await http.post(`/purchases/${id}/resend-stock`, {}, { params: { apply: apply ? 1 : 0, debug: debug ? 1 : 0 } })
  return r.data as { status: string; mode: 'apply' | 'preview'; applied_deltas?: { product_id: number; product_title?: string | null; line_title?: string | null; supplier_sku?: string | null; delta: number; new: number; old: number }[]; unresolved_lines?: number[] }
}

export async function cancelPurchase(id: number, note: string) {
  const r = await http.post(`/purchases/${id}/cancel`, { note })
  return r.data
}

export async function rollbackPurchase(id: number) {
  const r = await http.post(`/purchases/${id}/rollback`, {})
  return r.data as { status: string; reverted?: { product_id: number; delta: number }[] }
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

// POP Email importer (sin PDF). Puede recibir .eml o contenido pegado.
export async function importPopEmail(params: { supplier_id: number; kind?: 'eml' | 'html' | 'text'; file?: File; text?: string; }) {
  const kind = params.kind || (params.file ? 'eml' : (params.text ? 'html' : 'text'))
  if (kind === 'eml') {
    if (!params.file) throw new Error('Falta file (.eml)')
    const fd = new FormData()
    fd.append('file', params.file)
    const r = await http.post(`/purchases/import/pop-email`, fd, { params: { supplier_id: params.supplier_id, kind } })
    return r.data as { purchase_id: number; status: string; parsed: any }
  } else {
    const r = await http.post(`/purchases/import/pop-email`, { text: params.text || '' }, { params: { supplier_id: params.supplier_id, kind } })
    return r.data as { purchase_id: number; status: string; parsed: any }
  }
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

// iAVaL (IA Validator) services - Ahora usa Vision AI para mejor precisión
export async function iavalPreview(id: number) {
  // Usar endpoint Vision para extracción visual del PDF
  const r = await http.post(`/purchases/${id}/iaval/vision`, {})
  return r.data as {
    ok: boolean
    correlation_id: string
    proposal: { header: any; lines: any[] }
    diff: { header: any; lines: any[]; lines_new?: any[] }
    confidence: number
    comments: string[]
    applied: any
    audit: { image: string; prompt: string; response: string }
  }
}

export async function iavalApply(id: number, proposal: any, emitLog?: boolean) {
  // Si ya usamos Vision con apply=1, no necesitamos este paso adicional
  // Pero lo mantenemos para compatibilidad con el flujo existente
  const r = await http.post(`/purchases/${id}/iaval/vision`, {}, { params: { apply: 1 } })
  return r.data as { ok: boolean; applied: any; correlation_id?: string }
}

// Versión legacy (textual) - usar si Vision falla
export async function iavalPreviewLegacy(id: number) {
  const r = await http.post(`/purchases/${id}/iaval/preview`, {})
  return r.data as { proposal: any; diff: { header: any; lines: any[] }; confidence: number; comments: string[]; raw: string }
}

export async function iavalApplyLegacy(id: number, proposal: any, emitLog?: boolean) {
  const r = await http.post(`/purchases/${id}/iaval/apply`, { proposal }, { params: { emit_log: emitLog ? 1 : 0 } })
  return r.data as { ok: boolean; applied: any; log?: { filename: string; path: string; csv_filename?: string | null; url_json?: string; url_csv?: string | null } }
}

