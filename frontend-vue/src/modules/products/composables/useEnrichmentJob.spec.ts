// NG-HEADER: Nombre de archivo: useEnrichmentJob.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/composables/useEnrichmentJob.spec.ts
// NG-HEADER: Descripción: Verifica polling y cancelación al desmontar Enrich v2.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  create: vi.fn(),
  get: vi.fn(),
  apply: vi.fn(),
  discard: vi.fn(),
}))

vi.mock('../api/products', () => ({
  createEnrichmentJob: api.create,
  getEnrichmentJob: api.get,
  applyEnrichmentJob: api.apply,
  discardEnrichmentJob: api.discard,
}))

import { useEnrichmentJob } from './useEnrichmentJob'

describe('useEnrichmentJob', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('cancela el polling al desmontar la vista', async () => {
    vi.useFakeTimers()
    api.create.mockResolvedValue({ job_id: 'job-1', status: 'queued', status_url: '/status' })
    api.get.mockResolvedValue({
      job_id: 'job-1',
      canonical_product_id: 10,
      requested_product_id: 2,
      status: 'running',
      stage: 'research',
      scope: 'full',
      provider: null,
      model: null,
      proposal: null,
      confidence: null,
      evidence_by_field: null,
      provider_diagnostics: [],
      sources: [],
      applied_fields: [],
      error: null,
      attempts: 1,
      created_at: null,
      started_at: null,
      completed_at: null,
    })
    let enrichment!: ReturnType<typeof useEnrichmentJob>
    const Host = defineComponent({
      setup() {
        enrichment = useEnrichmentJob(async () => undefined)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)
    await enrichment.start(10, 2, 'full')
    expect(api.get).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(2_000)
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('recupera el último job al volver a abrir la ficha', async () => {
    api.get.mockResolvedValue({
      job_id: 'job-existing',
      status: 'failed',
      provider_diagnostics: [],
    })
    let enrichment!: ReturnType<typeof useEnrichmentJob>
    const Host = defineComponent({
      setup() {
        enrichment = useEnrichmentJob(async () => undefined)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)

    await enrichment.resume(10, 'job-existing')

    expect(api.get).toHaveBeenCalledWith(10, 'job-existing')
    expect(enrichment.job.value?.job_id).toBe('job-existing')
    wrapper.unmount()
  })
})
