// NG-HEADER: Nombre de archivo: shortages.ts
// NG-HEADER: Ubicación: frontend/src/services/shortages.ts
// NG-HEADER: Descripción: Servicio API para gestión de faltantes de stock
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export type ShortageReason = 'GIFT' | 'PENDING_SALE' | 'UNKNOWN'
export type ShortageStatus = 'OPEN' | 'RECONCILED'

export interface CreateShortagePayload {
    product_id: number
    quantity: number
    reason: ShortageReason
    observation?: string
}

export interface ShortageItem {
    id: number
    product_id: number
    product_title: string
    quantity: number
    reason: ShortageReason
    status: ShortageStatus
    observation?: string
    user_name?: string
    created_at: string
}

export interface ShortagesListResponse {
    items: ShortageItem[]
    total: number
    page: number
    pages: number
}

export interface ShortagesStatsResponse {
    total_items: number
    total_quantity: number
    by_reason: Record<string, number>
    this_month: number
}

export interface ListShortagesParams {
    reason?: ShortageReason
    status?: ShortageStatus
    product_id?: number
    date_from?: string
    date_to?: string
    page?: number
    page_size?: number
}

/**
 * Crear un nuevo reporte de faltante
 */
export async function createShortage(data: CreateShortagePayload) {
    const res = await http.post('/stock/shortages', data)
    return res.data
}

/**
 * Listar faltantes con filtros y paginación
 */
export async function listShortages(params: ListShortagesParams = {}): Promise<ShortagesListResponse> {
    const res = await http.get('/stock/shortages', { params })
    return res.data
}

/**
 * Obtener estadísticas de faltantes para dashboard
 */
export async function getShortagesStats(): Promise<ShortagesStatsResponse> {
    const res = await http.get('/stock/shortages/stats')
    return res.data
}

/**
 * Labels legibles para los motivos
 */
export const REASON_LABELS: Record<ShortageReason, string> = {
    GIFT: 'Regalo',
    PENDING_SALE: 'Venta Pendiente',
    UNKNOWN: 'Desconocido',
}

/**
 * Labels legibles para los estados
 */
export const STATUS_LABELS: Record<ShortageStatus, string> = {
    OPEN: 'Abierto',
    RECONCILED: 'Conciliado',
}
