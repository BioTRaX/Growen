// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/types.ts
// NG-HEADER: Descripción: Contratos tipados del módulo Vue de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md

export type PricePosition = 'much_cheaper' | 'very_cheaper' | 'moderately_cheaper' | 'slightly_cheaper' | 'aligned' | 'slightly_expensive' | 'moderately_expensive' | 'very_expensive' | 'unavailable'
export type MarketJobStatus = 'queued' | 'running' | 'partial' | 'succeeded' | 'failed' | 'cancelled'

export interface MarketProduct {
  product_id: number; internal_product_id: number | null; preferred_name: string; product_sku: string
  sale_price: number | null; market_price_reference: number | null; market_price_min: number | null; market_price_max: number | null
  last_market_update: string | null; price_delta_pct: number | null; price_position: PricePosition; comparison_label: string
  effective_sources_count: number; stale_sources_count: number; warning_sources_count: number; last_job_status: MarketJobStatus | null
  has_active_alerts: boolean; active_alerts_count: number; category_id: number | null; category_name: string | null
  supplier_id: number | null; supplier_name: string | null
}
export interface MarketProductPage { items: MarketProduct[]; total: number; page: number; page_size: number; pages: number }
export interface MarketFilters { q: string; category_id: number | null; supplier_id: number | null; page: number; page_size: number }
export interface MarketSource {
  id: number; source_name: string; url: string | null; currency: 'ARS'; source_type: 'static' | 'dynamic' | 'manual'
  last_price: number | null; last_checked_at: string | null; is_mandatory: boolean; is_active: boolean
  validation_status: 'verified' | 'warning' | 'rejected'; ars_confirmed: boolean | null; argentina_delivery_confirmed: boolean | null
  last_error_code: string | null; last_error_message: string | null; created_at: string; updated_at: string
}
export interface ProductSources {
  product_id: number; product_name: string; sale_price: number | null; market_price_reference: number | null
  market_price_updated_at: string | null; market_price_min: number | null; market_price_max: number | null
  mandatory: MarketSource[]; additional: MarketSource[]
}
export interface MarketJobItem { id: number; product_id: number; status: MarketJobStatus; attempts: number; sources_total: number; sources_succeeded: number; sources_failed: number; market_price_reference: number | null; error_code: string | null; error_message: string | null }
export interface MarketJob { id: string; trigger: string; status: MarketJobStatus; total_items: number; processed_items: number; success_count: number; error_count: number; created_at: string; started_at: string | null; completed_at: string | null; items: MarketJobItem[] }
export interface EnqueueResult { status: string; product_id: number; job_id: string; market_job_id: string; item_id: number; deduplicated: boolean; message: string }
export interface HistoryPoint { id: number; source_id: number | null; source_name: string | null; price: number; currency: 'ARS'; observation_type: 'source' | 'reference'; capture_method: string; created_at: string }
