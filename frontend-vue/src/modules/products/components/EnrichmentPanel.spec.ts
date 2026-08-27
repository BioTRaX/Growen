// NG-HEADER: Nombre de archivo: EnrichmentPanel.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/EnrichmentPanel.spec.ts
// NG-HEADER: Descripción: Verifica la visualización segura de diagnósticos de Enrich.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import EnrichmentPanel from './EnrichmentPanel.vue'
import type { EnrichmentJob } from '../types'

describe('EnrichmentPanel', () => {
  it('muestra código, HTTP y request ID sin requerir el mensaje remoto', async () => {
    const job: EnrichmentJob = {
      job_id: 'job-1',
      canonical_product_id: 5,
      requested_product_id: 18,
      status: 'failed',
      stage: null,
      scope: 'full',
      provider: null,
      model: null,
      proposal: null,
      confidence: null,
      evidence_by_field: null,
      sources: [],
      applied_fields: [],
      error: { code: 'ai_provider_unavailable', message: 'No hay proveedor IA válido' },
      attempts: 3,
      created_at: null,
      started_at: null,
      completed_at: null,
      provider_diagnostics: [{
        provider: 'openai',
        model: 'gpt-4.1-mini',
        status: 'failed',
        code: 'insufficient_quota',
        error_type: 'RateLimitError',
        http_status: 429,
        request_id: 'req_test_123',
        client_request_id: 'growen-enrich-job-1-openai',
        rate_limits: { remaining_requests: '0', reset_requests: '2s' },
        retryable: true,
        job_attempt: 3,
        recorded_at: '2026-08-18T00:00:00Z',
      }],
    }
    const wrapper = mount(EnrichmentPanel, {
      props: { job, loading: false, error: '' },
      global: { plugins: [vuetify] },
    })

    await wrapper.get('.v-expansion-panel-title').trigger('click')

    expect(wrapper.text()).toContain('OpenAI · insufficient_quota')
    expect(wrapper.text()).toContain('HTTP 429')
    expect(wrapper.text()).toContain('req_test_123')
    expect(wrapper.text()).toContain('remaining_requests=0')
  })
})
