export interface ProductSearchParams {
  q?: string
  supplier_id?: number
  category_id?: number
  page?: number
  page_size?: number
}

export interface ProductItem {
  product_id: number
  name: string
  supplier: { id: number; slug: string; name: string }
  precio_compra: number | null
  precio_venta: number | null
  compra_minima: number | null
  category_path: string
  stock: number
  updated_at: string | null
  canonical_product_id: number | null
}

export interface ProductSearchResponse {
  page: number
  page_size: number
  total: number
  items: ProductItem[]
}

import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function searchProducts(params: ProductSearchParams): Promise<ProductSearchResponse> {
  const url = new URL(base + '/products', window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  })
  const res = await fetch(url.toString(), {
    credentials: 'include',
    headers: csrfHeaders(),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateStock(productId: number, stock: number): Promise<{ product_id: number; stock: number }> {
  const headers = {
    ...csrfHeaders(),
    'Content-Type': 'application/json',
  }
  const res = await fetch(`${base}/products/${productId}/stock`, {
    method: 'PATCH',
    headers,
    credentials: 'include',
    body: JSON.stringify({ stock }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
