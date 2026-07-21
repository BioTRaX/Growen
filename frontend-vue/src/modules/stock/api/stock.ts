// NG-HEADER: Nombre de archivo: stock.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/api/stock.ts
// NG-HEADER: Descripción: Cliente HTTP tipado del módulo Vue de Stock y Faltantes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from '../../../services/http'
import { listProducts } from '../../products/api/products'
import type { ProductListResponse } from '../../products/types'
import type { CreateShortagePayload, ShortageReason, ShortageStats, ShortagesResponse, StockFilters } from '../types'

export async function listStock(filters: StockFilters, signal?: AbortSignal): Promise<ProductListResponse> {
  return listProducts({ ...filters, type: 'all', recent: '' }, signal)
}

function exportParams(filters: StockFilters): Record<string, string | number> {
  return {
    ...(filters.q.trim() ? { q: filters.q.trim() } : {}),
    ...(filters.supplier_id ? { supplier_id: filters.supplier_id } : {}),
    ...(filters.category_id ? { category_id: filters.category_id } : {}),
    stock: filters.stock,
    type: 'all',
    sort_by: 'updated_at',
    order: 'desc',
  }
}

export async function downloadStockExport(format: 'xlsx' | 'csv' | 'tiendanegocio', filters: StockFilters): Promise<void> {
  const suffix = format === 'tiendanegocio' ? 'export-tiendanegocio.xlsx' : `export.${format}`
  const filename = format === 'tiendanegocio' ? 'productos_tiendanegocio.xlsx' : `stock.${format}`
  const response = await http.get<Blob>(`/stock/${suffix}`, { params: exportParams(filters), responseType: 'blob' })
  const href = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export async function openStockPdf(filters: StockFilters): Promise<void> {
  const response = await http.get<Blob>('/stock/export.pdf', { params: exportParams(filters), responseType: 'blob' })
  const href = URL.createObjectURL(response.data)
  window.open(href, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(href), 60_000)
}

export async function listShortages(params: { page: number; page_size: number; reason?: ShortageReason }, signal?: AbortSignal): Promise<ShortagesResponse> {
  return (await http.get<ShortagesResponse>('/stock/shortages', { params, signal })).data
}

export async function getShortageStats(): Promise<ShortageStats> {
  return (await http.get<ShortageStats>('/stock/shortages/stats')).data
}

export async function createShortage(payload: CreateShortagePayload): Promise<{ id: number; new_stock: number; warning?: string }> {
  return (await http.post('/stock/shortages', payload)).data
}
