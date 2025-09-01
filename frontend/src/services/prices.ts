// NG-HEADER: Nombre de archivo: prices.ts
// NG-HEADER: Ubicación: frontend/src/services/prices.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
export interface PriceHistoryParams {
  supplier_product_id?: number
  product_id?: number
  page?: number
  page_size?: number
}

export interface PriceHistoryItem {
  as_of_date: string
  purchase_price: number | null
  sale_price: number | null
  delta_purchase_pct: number | null
  delta_sale_pct: number | null
}

export interface PriceHistoryResponse {
  page: number
  page_size: number
  total: number
  items: PriceHistoryItem[]
}

import { baseURL as base } from './http'

export async function getPriceHistory(
  params: PriceHistoryParams,
): Promise<PriceHistoryResponse> {
  const url = new URL(base + '/price-history', window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
  })
  const res = await fetch(url.toString(), { credentials: 'include' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
