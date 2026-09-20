// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/knowledge/types.ts
// NG-HEADER: Descripción: Contratos del Centro de Conocimiento Canónico.
// NG-HEADER: Lineamientos: Ver AGENTS.md

export type KnowledgeAssetType = 'web' | 'document' | 'image' | 'video'
export type KnowledgeStatus = 'pending' | 'confirmed' | 'archived'

export interface KnowledgeLocation {
  id: number
  url: string | null
  storage_path: string | null
  mime_type: string | null
  content_hash: string | null
  content_version: number
  status: string
  is_primary: boolean
  metadata: Record<string, unknown> | null
  last_fetched_at: string | null
  error: string | null
}

export interface KnowledgeMarketProfile {
  id: number
  last_price: number | null
  last_checked_at: string | null
  is_mandatory: boolean
  is_active: boolean
  validation_status: string
  ars_confirmed: boolean | null
  argentina_delivery_confirmed: boolean | null
  currency: string | null
  source_type: string | null
}

export interface KnowledgeAsset {
  id: number
  canonical_product_id: number
  title: string
  asset_type: KnowledgeAssetType
  status: KnowledgeStatus
  origin: string
  labels: string[]
  capabilities: string[]
  exclude_from_enrichment: boolean
  trust_score: number
  trust_breakdown: Record<string, unknown> | null
  ai_trust_adjustment: number | null
  ai_trust_reason: Record<string, unknown> | null
  revision: number
  archived_at: string | null
  locations: KnowledgeLocation[]
  market: KnowledgeMarketProfile | null
  created_at: string
  updated_at: string
}

export interface KnowledgeResponse {
  canonical_product_id: number
  summary: {
    total: number
    confirmed: number
    pending: number
    archived: number
    by_type: Record<KnowledgeAssetType, number>
  }
  items: KnowledgeAsset[]
}

export interface KnowledgeCapability {
  code: string
  name: string
  description: string | null
  is_active: boolean
}

export interface KnowledgeFact {
  id: number
  fact_key: string
  capability: string
  value: Record<string, unknown>
  confidence: number
  status: string
  supporting_claim_ids: number[]
  revision: number
}

export interface KnowledgeEvent {
  id: number
  asset_id: number | null
  event_type: string
  actor_user_id: number | null
  payload: Record<string, unknown> | null
  created_at: string
}

export interface KnowledgeJob {
  id: string
  asset_id: number
  status: string
  stage: string | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
}

