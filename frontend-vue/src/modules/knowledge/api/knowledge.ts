// NG-HEADER: Nombre de archivo: knowledge.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/knowledge/api/knowledge.ts
// NG-HEADER: Descripción: Cliente HTTP del Centro de Conocimiento Canónico.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { http } from '../../../services/http'
import type {
  KnowledgeAsset,
  KnowledgeAssetType,
  KnowledgeCapability,
  KnowledgeEvent,
  KnowledgeFact,
  KnowledgeJob,
  KnowledgeResponse,
} from '../types'

export interface KnowledgeCreatePayload {
  title: string
  asset_type: KnowledgeAssetType
  url: string | null
  labels: string[]
  capabilities: string[]
  exclude_from_enrichment: boolean
  market_is_active: boolean
  market_is_mandatory: boolean
  market_source_type: 'static' | 'dynamic'
  market_argentina_delivery_confirmed: boolean
}

export async function getKnowledge(productId: number, includeArchived = false): Promise<KnowledgeResponse> {
  return (await http.get<KnowledgeResponse>(`/canonical-products/${productId}/knowledge`, {
    params: { include_archived: includeArchived },
  })).data
}

export async function createKnowledge(productId: number, payload: KnowledgeCreatePayload): Promise<KnowledgeAsset> {
  return (await http.post<KnowledgeAsset>(`/canonical-products/${productId}/knowledge`, payload)).data
}

export async function updateKnowledge(productId: number, asset: KnowledgeAsset, payload: Partial<KnowledgeCreatePayload>): Promise<KnowledgeAsset> {
  return (await http.patch<KnowledgeAsset>(`/canonical-products/${productId}/knowledge/${asset.id}`, {
    expected_revision: asset.revision,
    title: payload.title,
    labels: payload.labels,
    capabilities: payload.capabilities,
    exclude_from_enrichment: payload.exclude_from_enrichment,
    market_is_active: payload.market_is_active,
    market_is_mandatory: payload.market_is_mandatory,
    market_source_type: payload.market_source_type,
    market_argentina_delivery_confirmed: payload.market_argentina_delivery_confirmed,
  })).data
}

export async function archiveKnowledge(productId: number, assetId: number): Promise<void> {
  await http.delete(`/canonical-products/${productId}/knowledge/${assetId}`)
}

export async function restoreKnowledge(productId: number, assetId: number): Promise<KnowledgeAsset> {
  return (await http.post<KnowledgeAsset>(`/canonical-products/${productId}/knowledge/${assetId}/restore`)).data
}

export async function processKnowledge(productId: number, assetId: number): Promise<{ job_id: string; status: string }> {
  return (await http.post(`/canonical-products/${productId}/knowledge/${assetId}/process`)).data
}

export async function getKnowledgeCapabilities(): Promise<KnowledgeCapability[]> {
  return (await http.get<{ items: KnowledgeCapability[] }>('/knowledge-capabilities')).data.items
}

export async function getKnowledgeFacts(productId: number): Promise<KnowledgeFact[]> {
  return (await http.get<{ items: KnowledgeFact[] }>(`/canonical-products/${productId}/knowledge/facts`)).data.items
}

export async function getKnowledgeHistory(productId: number): Promise<KnowledgeEvent[]> {
  return (await http.get<{ items: KnowledgeEvent[] }>(`/canonical-products/${productId}/knowledge/history`)).data.items
}

export async function getKnowledgeJobs(productId: number): Promise<KnowledgeJob[]> {
  return (await http.get<{ items: KnowledgeJob[] }>(`/canonical-products/${productId}/knowledge/jobs`)).data.items
}

export async function uploadKnowledge(
  productId: number,
  file: File,
  title: string,
  labels: string[],
  capabilities: string[],
): Promise<KnowledgeAsset> {
  const body = new FormData()
  body.append('file', file)
  return (await http.post<KnowledgeAsset>(`/canonical-products/${productId}/knowledge/upload`, body, {
    params: { title, labels: labels.join(','), capabilities: capabilities.join(',') },
  })).data
}
