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
  data: { name: string; brand?: string | null; specs_json?: any | null },
): Promise<CanonicalProduct> {
  const res = await http.post('/canonical-products', data)
  return res.data
}

export async function updateCanonicalProduct(
  id: number,
  data: { name?: string; brand?: string | null; specs_json?: any | null },
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
