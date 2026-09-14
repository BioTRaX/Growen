// NG-HEADER: Nombre de archivo: catalogAudit.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/api/catalogAudit.spec.ts
// NG-HEADER: Descripción: Contrato HTTP del auditor autónomo de catálogo.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { http } from '../../../services/http'
import { cancelCatalogAudit, createCatalogAudit, getCatalogAudit, resolveCatalogAuditItem } from './catalogAudit'

vi.mock('../../../services/http', () => ({ http: { get: vi.fn(), post: vi.fn() } }))

describe('catalogAudit api', () => {
  beforeEach(() => vi.clearAllMocks())

  it('envía selección canónica única y opciones explícitas', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { run_id: 'run-1', status: 'queued', status_url: '/run-1' } })
    await createCatalogAudit({ scope: 'selected', canonical_product_ids: [3, 3, 8], include_orphans: true, mode: 'full', enrich_missing: true, auto_fix: false })
    expect(http.post).toHaveBeenCalledWith('/canonical-products/catalog-audits', {
      scope: 'selected', canonical_product_ids: [3, 8], include_orphans: true, mode: 'full', enrich_missing: true, auto_fix: false,
    })
  })

  it('consulta y cancela por run', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { run_id: 'run-1' } })
    vi.mocked(http.post).mockResolvedValue({ data: {} })
    await getCatalogAudit('run-1')
    await cancelCatalogAudit('run-1')
    expect(http.get).toHaveBeenCalledWith('/canonical-products/catalog-audits/run-1', expect.anything())
    expect(http.post).toHaveBeenCalledWith('/canonical-products/catalog-audits/run-1/cancel')
  })

  it('devuelve el nuevo run al aplicar una corrección y reauditar', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { item: { item_id: 9 }, new_run_id: 'run-2' } })

    const result = await resolveCatalogAuditItem('run-1', 9, {
      action: 'apply_correction', note: 'Corrección verificada', expected_content_revision: 4,
      corrections: { description_html: '<p>Ficha corregida</p>' },
    })

    expect(http.post).toHaveBeenCalledWith('/canonical-products/catalog-audits/run-1/items/9/resolve', {
      action: 'apply_correction', note: 'Corrección verificada', expected_content_revision: 4,
      corrections: { description_html: '<p>Ficha corregida</p>' },
    })
    expect(result.new_run_id).toBe('run-2')
  })
})
