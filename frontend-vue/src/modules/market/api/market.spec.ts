// NG-HEADER: Nombre de archivo: market.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/api/market.spec.ts
// NG-HEADER: Descripción: Contratos HTTP del pipeline automático de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { beforeEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
vi.mock('../../../services/http', () => ({ http }))

import { forceDetectMarketSourcePrice, manuallyValidateMarketSource, refreshProduct, refreshProducts, restoreMarketSource, updateMarketSource } from './market'

describe('cliente HTTP del pipeline de Mercado', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    http.post.mockResolvedValue({ data: { results: [] } })
  })

  it('solicita descubrimiento y extracción masivos con opción de redescubrimiento', async () => {
    await refreshProducts([1, 2, 2], true)
    expect(http.post).toHaveBeenCalledWith('/market/products/batch-refresh', {
      product_ids: [1, 2, 2],
      force_rediscovery: true,
    })
  })

  it('permite forzar redescubrimiento individual y restaurar una fuente', async () => {
    await refreshProduct(7, true)
    expect(http.post).toHaveBeenCalledWith('/market/products/7/refresh-market', {
      force_rediscovery: true,
    })
    await restoreMarketSource(31)
    expect(http.post).toHaveBeenCalledWith('/market/sources/31/restore')
    http.patch.mockResolvedValue({ data: {} })
    await updateMarketSource(31, { source_name: 'Competidor', url: 'https://example.com/p', source_type: 'static', is_mandatory: false })
    expect(http.patch).toHaveBeenCalledWith('/market/sources/31', { source_name: 'Competidor', url: 'https://example.com/p', source_type: 'static', is_mandatory: false })
  })

  it('encola la detección forzada para una única fuente', async () => {
    http.post.mockResolvedValueOnce({ data: { job_id: 'job-1', item_id: 9 } })

    await forceDetectMarketSourcePrice(31)

    expect(http.post).toHaveBeenCalledWith('/market/sources/31/detect-price')
  })

  it('envía las confirmaciones y evidencia de la validación manual', async () => {
    http.post.mockResolvedValueOnce({ data: { source_id: 31, is_active: true } })

    await manuallyValidateMarketSource(31, {
      ars_confirmed: true,
      argentina_delivery_confirmed: true,
      evidence_note: 'La ficha muestra precio final ARS y envíos a todo el país.',
    })

    expect(http.post).toHaveBeenCalledWith('/market/sources/31/manual-validation', {
      ars_confirmed: true,
      argentina_delivery_confirmed: true,
      evidence_note: 'La ficha muestra precio final ARS y envíos a todo el país.',
    })
  })
})
