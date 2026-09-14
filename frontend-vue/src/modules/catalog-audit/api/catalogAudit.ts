// NG-HEADER: Nombre de archivo: catalogAudit.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/api/catalogAudit.ts
// NG-HEADER: Descripción: Cliente HTTP del auditor autónomo de catálogo.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from '../../../services/http'
import type {
  CatalogAuditCreated, CatalogAuditOptions, CatalogAuditPreflight, CatalogAuditResolution,
  CatalogAuditResolutionResult, CatalogAuditRun,
} from '../types'

export async function createCatalogAudit(options: CatalogAuditOptions): Promise<CatalogAuditCreated> {
  const payload = { ...options, canonical_product_ids: options.canonical_product_ids ? [...new Set(options.canonical_product_ids)] : undefined }
  return (await http.post<CatalogAuditCreated>('/canonical-products/catalog-audits', payload)).data
}
export async function listCatalogAudits(signal?: AbortSignal): Promise<CatalogAuditRun[]> {
  return (await http.get<{ items: CatalogAuditRun[] }>('/canonical-products/catalog-audits', { signal })).data.items
}
export async function getCatalogAudit(runId: string, signal?: AbortSignal): Promise<CatalogAuditRun> {
  return (await http.get<CatalogAuditRun>(`/canonical-products/catalog-audits/${runId}`, { signal })).data
}
export async function getCatalogAuditPreflight(signal?: AbortSignal): Promise<CatalogAuditPreflight> {
  return (await http.get<CatalogAuditPreflight>('/canonical-products/catalog-audits/preflight', { signal })).data
}
export async function cancelCatalogAudit(runId: string): Promise<void> {
  await http.post(`/canonical-products/catalog-audits/${runId}/cancel`)
}
export async function retryCatalogAudit(runId: string): Promise<void> {
  await http.post(`/canonical-products/catalog-audits/${runId}/retry`)
}
export async function resolveCatalogAuditItem(runId: string, itemId: number, payload: CatalogAuditResolution): Promise<CatalogAuditResolutionResult> {
  return (await http.post<CatalogAuditResolutionResult>(`/canonical-products/catalog-audits/${runId}/items/${itemId}/resolve`, payload)).data
}
