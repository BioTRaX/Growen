// NG-HEADER: Nombre de archivo: enrichment.spec.ts
// NG-HEADER: Ubicación: frontend/src/services/enrichment.spec.ts
// NG-HEADER: Descripción: Pruebas del contrato canónico de batches de enriquecimiento.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from './http'
import { enqueueCanonicalEnrichment } from './enrichment'

vi.mock('./http')

describe('enqueueCanonicalEnrichment', () => {
  beforeEach(() => vi.resetAllMocks())

  it('clasifica por producto los jobs aceptados, fallidos y omitidos', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: {
        batch_id: 'batch-1',
        jobs: [
          { product_id: 11, canonical_product_id: 101, job_id: 'job-1', status: 'queued', error: null },
          { product_id: 12, canonical_product_id: 102, job_id: 'job-2', status: 'pending', error: 'Enrich deshabilitado' },
        ],
        skipped: [{ product_id: 13, reason: 'canonical_required' }],
      },
    })

    const outcome = await enqueueCanonicalEnrichment([11, 12, 13], 'react-test')

    expect(http.post).toHaveBeenCalledWith('/canonical-products/enrichment-batches', {
      client_request_id: expect.stringMatching(/^(react-test-|[0-9a-f-]{36})/),
      product_ids: [11, 12, 13],
      scope: 'full',
    })
    expect(outcome.acceptedIds).toEqual([11])
    expect(outcome.failedIds).toEqual([12, 13])
    expect(outcome.failures).toEqual([
      { productId: 12, reason: 'Enrich deshabilitado' },
      { productId: 13, reason: 'El producto no tiene un canónico asignado' },
    ])
  })

  it('trata una respuesta sin resultado para un ID como fallo seguro', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({
      data: { batch_id: 'batch-empty', jobs: [], skipped: [] },
    })

    const outcome = await enqueueCanonicalEnrichment([21], 'react-test')

    expect(outcome.acceptedIds).toEqual([])
    expect(outcome.failedIds).toEqual([21])
    expect(outcome.failures[0]?.reason).toBe('El backend no informó el resultado del producto')
  })
})
