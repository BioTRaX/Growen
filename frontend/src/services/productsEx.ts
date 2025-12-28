// NG-HEADER: Nombre de archivo: productsEx.ts
// NG-HEADER: Ubicación: frontend/src/services/productsEx.ts
// NG-HEADER: Descripción: Servicios HTTP para productos extendidos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { baseURL as base } from './http'

function csrfHeaders(): Record<string, string> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
}

export async function updateSalePrice(
  productId: number,
  sale_price: number,
  note?: string,
): Promise<{ id: number; sale_price: number | null }> {
  const res = await fetch(`${base}/products-ex/products/${productId}/sale-price`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ sale_price, note }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateCanonicalSku(
  canonicalProductId: number,
  sku_custom: string,
): Promise<{ id: number; sku_custom: string | null }> {
  const res = await fetch(`${base}/canonical-products/${canonicalProductId}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ sku_custom }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function updateSupplierBuyPrice(
  supplierItemId: number,
  buy_price: number,
  note?: string,
): Promise<{ id: number; buy_price: number | null }> {
  const res = await fetch(`${base}/products-ex/supplier-items/${supplierItemId}/buy-price`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ buy_price, note }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateSupplierSalePrice(
  supplierItemId: number,
  sale_price: number,
  note?: string,
): Promise<{ id: number; sale_price: number | null }> {
  const res = await fetch(`${base}/products-ex/supplier-items/${supplierItemId}/sale-price`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ sale_price, note }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export type BulkMode = 'set' | 'inc' | 'dec' | 'inc_pct' | 'dec_pct'

export async function bulkUpdateSalePrice(
  payload: { product_ids: number[]; mode: BulkMode; value: number; note?: string },
): Promise<{ updated: number }> {
  const res = await fetch(`${base}/products-ex/products/bulk-sale-price`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export interface OfferingRow {
  supplier_item_id: number
  supplier_name: string
  supplier_sku: string
  buy_price: number | null
  updated_at: string | null
}

export async function getProductOfferings(productId: number): Promise<OfferingRow[]> {
  const res = await fetch(`${base}/products-ex/products/${productId}/offerings`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getInternalProductOfferings(productId: number): Promise<OfferingRow[]> {
  const res = await fetch(`${base}/products-ex/products/internal/${productId}/offerings`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export interface ProductsTablePrefs {
  columnOrder?: string[]
  columnVisibility?: Record<string, boolean>
  columnWidths?: Record<string, number>
}

export async function getProductsTablePrefs(): Promise<ProductsTablePrefs> {
  const res = await fetch(`${base}/products-ex/users/me/preferences/products-table`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function putProductsTablePrefs(prefs: ProductsTablePrefs): Promise<{ status: string }> {
  const res = await fetch(`${base}/products-ex/users/me/preferences/products-table`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify(prefs),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// Product detail (card) style preference
export type ProductDetailStyle = 'default' | 'minimalDark'

export async function getProductDetailStylePref(): Promise<{ style?: ProductDetailStyle }> {
  const res = await fetch(`${base}/products-ex/users/me/preferences/product-detail`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function putProductDetailStylePref(style: ProductDetailStyle): Promise<{ status: string }> {
  const res = await fetch(`${base}/products-ex/users/me/preferences/product-detail`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
    body: JSON.stringify({ style }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
