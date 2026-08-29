// NG-HEADER: Nombre de archivo: enrichment.ts
// NG-HEADER: Ubicación: frontend/src/services/enrichment.ts
// NG-HEADER: Descripción: Cliente y clasificación de batches canónicos de enriquecimiento.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import http from './http'

export interface EnrichmentBatchFailure {
  productId: number
  reason: string
}

export interface EnrichmentBatchOutcome {
  acceptedIds: number[]
  failedIds: number[]
  failures: EnrichmentBatchFailure[]
}

interface EnrichmentBatchResponse {
  jobs?: Array<{ product_id?: number; error?: unknown }>
  skipped?: Array<{ product_id?: number; reason?: string }>
}

function describeDispatchError(error: unknown): string {
  if (typeof error === 'string' && error.trim()) return error
  if (error && typeof error === 'object') {
    const candidate = error as { detail?: unknown; message?: unknown }
    if (typeof candidate.detail === 'string' && candidate.detail.trim()) return candidate.detail
    if (typeof candidate.message === 'string' && candidate.message.trim()) return candidate.message
  }
  return 'El job no pudo enviarse a enriquecimiento'
}

function describeSkipped(reason: string | undefined): string {
  return reason === 'canonical_required'
    ? 'El producto no tiene un canónico asignado'
    : 'El producto fue omitido por el backend'
}

export async function enqueueCanonicalEnrichment(
  productIds: number[],
  requestPrefix: string,
): Promise<EnrichmentBatchOutcome> {
  const requestId = globalThis.crypto?.randomUUID?.() || `${requestPrefix}-${Date.now()}`
  const response = await http.post<EnrichmentBatchResponse>(
    '/canonical-products/enrichment-batches',
    { client_request_id: requestId, product_ids: productIds, scope: 'full' },
  )
  const accepted = new Set<number>()
  const failures = new Map<number, string>()

  for (const job of response.data?.jobs || []) {
    if (typeof job.product_id !== 'number') continue
    if (job.error) failures.set(job.product_id, describeDispatchError(job.error))
    else accepted.add(job.product_id)
  }
  for (const skipped of response.data?.skipped || []) {
    if (typeof skipped.product_id !== 'number') continue
    failures.set(skipped.product_id, describeSkipped(skipped.reason))
  }
  for (const productId of productIds) {
    if (!accepted.has(productId) && !failures.has(productId)) {
      failures.set(productId, 'El backend no informó el resultado del producto')
    }
  }

  const uniqueIds = [...new Set(productIds)]
  const acceptedIds = uniqueIds.filter((productId) => accepted.has(productId))
  const failedIds = uniqueIds.filter((productId) => failures.has(productId))
  return {
    acceptedIds,
    failedIds,
    failures: failedIds.map((productId) => ({ productId, reason: failures.get(productId)! })),
  }
}
