// NG-HEADER: Nombre de archivo: products.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/api/products.spec.ts
// NG-HEADER: Descripción: Verifica que el batch de Enrich use el contrato canónico.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it, vi } from 'vitest'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('../../../services/http', () => ({ http: { post } }))

import { enrichProducts } from './products'

describe('enrichProducts', () => {
  it('envía IDs al batch canónico y no al adaptador legacy', async () => {
    post.mockResolvedValueOnce({ data: { batch_id: 'batch-1', jobs: [], skipped: [] } })

    await enrichProducts([18, 19])

    expect(post).toHaveBeenCalledWith('/canonical-products/enrichment-batches', {
      client_request_id: expect.any(String),
      product_ids: [18, 19],
      scope: 'full',
    })
    expect(post).not.toHaveBeenCalledWith('/products/enrich-multiple', expect.anything())
  })
})
