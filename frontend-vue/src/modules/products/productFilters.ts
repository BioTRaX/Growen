// NG-HEADER: Nombre de archivo: productFilters.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/productFilters.ts
// NG-HEADER: Descripción: Parseo y serialización de filtros de Productos en la URL.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import type { ProductListFilters, ProductRecentFilter, ProductStockFilter, ProductTypeFilter } from './types'

export const DEFAULT_PRODUCT_FILTERS: ProductListFilters = {
  q: '',
  supplier_id: null,
  category_id: null,
  stock: '',
  recent: '',
  type: 'all',
  page: 1,
  page_size: 50,
}

function positiveInteger(value: unknown, fallback: number): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function optionalInteger(value: unknown): number | null {
  const parsed = positiveInteger(value, 0)
  return parsed || null
}

export function parseProductFilters(query: LocationQuery): ProductListFilters {
  const stock = query.stock === 'gt:0' || query.stock === 'eq:0' ? query.stock as ProductStockFilter : ''
  const type = ['all', 'canonical', 'supplier'].includes(String(query.type)) ? query.type as ProductTypeFilter : 'all'
  const recentValue = Number(query.recent)
  const recent = [1, 7, 30].includes(recentValue) ? recentValue as ProductRecentFilter : ''
  return {
    q: typeof query.q === 'string' ? query.q : '',
    supplier_id: optionalInteger(query.supplier_id),
    category_id: optionalInteger(query.category_id),
    stock,
    recent,
    type,
    page: positiveInteger(query.page, 1),
    page_size: positiveInteger(query.page_size, 50),
  }
}

export function serializeProductFilters(filters: ProductListFilters): LocationQueryRaw {
  const query: LocationQueryRaw = {}
  if (filters.q.trim()) query.q = filters.q.trim()
  if (filters.supplier_id) query.supplier_id = String(filters.supplier_id)
  if (filters.category_id) query.category_id = String(filters.category_id)
  if (filters.stock) query.stock = filters.stock
  if (filters.recent) query.recent = String(filters.recent)
  if (filters.type !== 'all') query.type = filters.type
  if (filters.page > 1) query.page = String(filters.page)
  if (filters.page_size !== 50) query.page_size = String(filters.page_size)
  return query
}
