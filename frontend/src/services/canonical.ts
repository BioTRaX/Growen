// NG-HEADER: Nombre de archivo: canonical.ts
// NG-HEADER: Ubicación: frontend/src/services/canonical.ts
// NG-HEADER: Descripción: Servicios HTTP para productos canónicos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export interface CanonicalOffer {
  supplier: { id: number; name: string; slug: string }
  precio_venta: number | null
  precio_compra: number | null
  compra_minima: number | null
  updated_at: string | null
  supplier_product_id: number
  mejor_precio: boolean
}

export interface CanonicalProduct {
  id: number
  ng_sku: string
  name: string
  brand: string | null
  specs_json: Record<string, any> | null
  sku_custom?: string | null
  category_id?: number | null
  subcategory_id?: number | null
}

import { baseURL as base } from './http'

export async function getCanonicalProduct(
  id: number,
): Promise<CanonicalProduct> {
  const res = await fetch(`${base}/canonical-products/${id}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createCanonicalProduct(
  data: { name: string; brand?: string | null; specs_json?: any | null; sku_custom?: string | null; category_id?: number | null; subcategory_id?: number | null },
): Promise<CanonicalProduct> {
  const res = await http.post('/canonical-products', data)
  return res.data
}

export async function updateCanonicalProduct(
  id: number,
  data: { name?: string; brand?: string | null; specs_json?: any | null; sku_custom?: string | null; category_id?: number | null; subcategory_id?: number | null },
): Promise<CanonicalProduct> {
  const res = await http.patch(`/canonical-products/${id}`, data)
  return res.data
}

export async function listOffersByCanonical(
  canonicalId: number,
): Promise<CanonicalOffer[]> {
  const res = await fetch(
    `${base}/canonical-products/${canonicalId}/offers`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function deleteCanonicalProduct(
  id: number,
): Promise<{ status: string; id: number }> {
  const res = await http.delete(`/canonical-products/${id}`)
  return res.data
}

export async function getNextSeq(category_id: number | null | undefined): Promise<number> {
  const params = new URLSearchParams()
  if (category_id) params.set('category_id', String(category_id))
  const res = await fetch(`${base}/catalog/next-seq?${params.toString()}`, { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const j = await res.json().catch(() => ({} as any))
  return Number(j?.next_seq ?? 1)
}

// ============================================================================
// BATCH CREATION
// ============================================================================

export interface CanonicalBatchItem {
  name: string
  brand?: string | null
  category_id?: number | null
  subcategory_id?: number | null
  sku_custom?: string | null
  source_product_id?: number | null
}

export interface CanonicalBatchResponse {
  status: string
  job_id: string
  message: string
  total_items: number
}

/**
 * Encola creación batch de productos canónicos.
 * @param items Lista de productos a crear
 * @returns job_id y metadata del job encolado
 */
export async function createCanonicalBatch(
  items: CanonicalBatchItem[],
): Promise<CanonicalBatchResponse> {
  const res = await http.post('/canonical-products/batch-job', { items })
  return res.data
}
