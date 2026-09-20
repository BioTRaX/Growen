// NG-HEADER: Nombre de archivo: TechnicalDashboardView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/TechnicalDashboardView.spec.ts
// NG-HEADER: Descripción: Verifica la observabilidad del auditor en el dashboard técnico.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const operations = vi.hoisted(() => ({
  getCatalogSummaries: vi.fn(), getChatStats: vi.fn(), getChatMetrics: vi.fn(),
  getEnrichmentSummary: vi.fn(), getImageJobStatus: vi.fn(), getKnowledgeStatus: vi.fn(),
  getSchedulerStatus: vi.fn(), getTechnicalHealth: vi.fn(), listDriveRuns: vi.fn(),
  listKnowledgeTasks: vi.fn(), listSchedulerRuns: vi.fn(),
}))
const auditApi = vi.hoisted(() => ({ getCatalogAuditSummary: vi.fn() }))
vi.mock('../../../services/adminOperations', () => operations)
vi.mock('../../catalog-audit/api/catalogAudit', () => auditApi)

import TechnicalDashboardView from './TechnicalDashboardView.vue'

describe('TechnicalDashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    operations.getTechnicalHealth.mockResolvedValue({ status: 'ok', details: {} })
    operations.getChatStats.mockResolvedValue({ total_sessions: 0, total_messages: 0, sessions_last_7_days: 0, avg_messages_per_session: 0 })
    operations.getChatMetrics.mockResolvedValue({})
    operations.listDriveRuns.mockResolvedValue({ items: [] })
    operations.getSchedulerStatus.mockResolvedValue({ working: false, enabled: false })
    operations.listSchedulerRuns.mockResolvedValue({ items: [] })
    operations.getCatalogSummaries.mockResolvedValue([])
    operations.getKnowledgeStatus.mockResolvedValue({ total_sources: 0, files_pending: 0, tasks_running: 0 })
    operations.listKnowledgeTasks.mockResolvedValue([])
    operations.getImageJobStatus.mockResolvedValue({ status: 'idle' })
    operations.getEnrichmentSummary.mockResolvedValue({
      worker: { status: 'stopped', ok: false, ready: 0, delayed: 0 },
      jobs: { total: 0, by_status: {}, recent: [] },
      catalog_coverage: { total_canonical: 29, enriched: 9, pending: 20 },
    })
    auditApi.getCatalogAuditSummary.mockResolvedValue({
      worker: { status: 'running', ok: true, broker_ok: true, ready: 2, delayed: 1 },
      runs: {
        total: 2, active: 2, by_status: { queued: 1, running: 1 },
        recent: [{ run_id: 'run-visible', status: 'running', total_items: 29, processed_items: 7, issue_items: 2 }],
      },
      items: { by_status: { pending: 20, auditing: 1 } },
      catalog_coverage: { total_canonical: 29, audited: 8, pending: 21, quarantined: 0 },
    })
  })

  it('presenta runs encolados y en curso con progreso', async () => {
    const wrapper = mount(TechnicalDashboardView, { global: { plugins: [createPinia(), vuetify] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Auditor de catálogo')
    expect(wrapper.text()).toContain('2 listos en Redis')
    expect(wrapper.text()).toContain('1 encolado')
    expect(wrapper.text()).toContain('1 en curso')
    expect(wrapper.text()).toContain('7 / 29')
    expect(wrapper.findAll('.v-btn').some((button) => button.text().trim() === 'Abrir auditor')).toBe(true)
  })
})
