// NG-HEADER: Nombre de archivo: market.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/api/market.ts
// NG-HEADER: Descripción: Cliente HTTP tipado del módulo Vue de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from '../../../services/http'
import type { EnqueueResult, HistoryPoint, ManualSourceValidationPayload, ManualSourceValidationResult, MarketFilters, MarketJob, MarketProductPage, MarketSource, ProductSources, SourcePriceDetectionResult } from '../types'

export async function listMarketProducts(filters: MarketFilters, signal?: AbortSignal): Promise<MarketProductPage> {
  const params = { page: filters.page, page_size: filters.page_size, ...(filters.q.trim() ? { q: filters.q.trim() } : {}), ...(filters.category_id ? { category_id: filters.category_id } : {}), ...(filters.supplier_id ? { supplier_id: filters.supplier_id } : {}) }
  return (await http.get<MarketProductPage>('/market/products', { params, signal })).data
}
export async function getProductSources(productId: number): Promise<ProductSources> { return (await http.get<ProductSources>(`/market/products/${productId}/sources`)).data }
export async function refreshProduct(productId: number, forceRediscovery = false): Promise<EnqueueResult> { return (await http.post<EnqueueResult>(`/market/products/${productId}/refresh-market`, { force_rediscovery: forceRediscovery })).data }
export async function refreshProducts(productIds: number[], forceRediscovery = false): Promise<{ results: Array<{ product_id: number; job_id: string | null; item_id: number | null; deduplicated: boolean; status: string }> }> { return (await http.post('/market/products/batch-refresh', { product_ids: productIds, force_rediscovery: forceRediscovery })).data }
export async function getMarketJob(jobId: string): Promise<MarketJob> { return (await http.get<MarketJob>(`/market/jobs/${jobId}`)).data }
export async function updateSalePrice(productId: number, salePrice: number): Promise<void> { await http.patch(`/market/products/${productId}/sale-price`, { sale_price: salePrice }) }
export async function getMarketHistory(productId: number): Promise<HistoryPoint[]> { return (await http.get<{ items: HistoryPoint[] }>(`/market/products/${productId}/history`)).data.items }
export async function addMarketSource(productId: number, payload: { source_name: string; url?: string | null; source_type: 'static' | 'dynamic' | 'manual'; is_mandatory: boolean; attested_argentina_delivery?: boolean }): Promise<MarketSource> { return (await http.post(`/market/products/${productId}/sources`, { ...payload, currency: 'ARS' })).data }
export async function deleteMarketSource(sourceId: number): Promise<void> { await http.delete(`/market/sources/${sourceId}`) }
export async function restoreMarketSource(sourceId: number): Promise<MarketSource> { return (await http.post<MarketSource>(`/market/sources/${sourceId}/restore`)).data }
export async function updateMarketSource(sourceId: number, payload: { source_name: string; url?: string | null; source_type: 'static' | 'dynamic' | 'manual'; is_mandatory: boolean }): Promise<MarketSource> { return (await http.patch<MarketSource>(`/market/sources/${sourceId}`, payload)).data }
export async function createManualObservation(sourceId: number, price: number, note?: string): Promise<{ market_price_reference: number | null }> { return (await http.post(`/market/sources/${sourceId}/observations`, { price, note })).data }
export async function revalidateMarketSource(sourceId: number): Promise<void> { await http.post(`/market/sources/${sourceId}/revalidate`) }
export async function forceDetectMarketSourcePrice(sourceId: number): Promise<SourcePriceDetectionResult> { return (await http.post<SourcePriceDetectionResult>(`/market/sources/${sourceId}/detect-price`)).data }
export async function manuallyValidateMarketSource(sourceId: number, payload: ManualSourceValidationPayload): Promise<ManualSourceValidationResult> { return (await http.post<ManualSourceValidationResult>(`/market/sources/${sourceId}/manual-validation`, payload)).data }
