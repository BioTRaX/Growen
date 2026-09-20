// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/stock/types.ts
// NG-HEADER: Descripción: Contratos del módulo Vue de Stock y Faltantes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
export type StockTab = 'gt:0' | 'eq:0'

export interface StockFilters {
  q: string
  supplier_id: number | null
  category_id: number | null
  stock: StockTab
  page: number
  page_size: number
}

export type ShortageReason = 'GIFT' | 'PENDING_SALE' | 'UNKNOWN'
export type ShortageStatus = 'OPEN' | 'RECONCILED'

export interface ShortageItem {
  id: number
  product_id: number
  product_title: string
  quantity: number
  reason: ShortageReason
  status: ShortageStatus
  observation: string | null
  user_name: string | null
  created_at: string
}

export interface ShortagesResponse { items: ShortageItem[]; total: number; page: number; pages: number }
export interface ShortageStats { total_items: number; total_quantity: number; by_reason: Record<string, number>; this_month: number }
export interface CreateShortagePayload { product_id: number; quantity: number; reason: ShortageReason; observation?: string }

export const SHORTAGE_REASON_LABELS: Record<ShortageReason, string> = {
  GIFT: 'Regalo',
  PENDING_SALE: 'Venta pendiente',
  UNKNOWN: 'Desconocido',
}
