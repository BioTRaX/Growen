// NG-HEADER: Nombre de archivo: WorkersView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/admin/views/WorkersView.spec.ts
// NG-HEADER: Descripción: Pruebas del runtime local y estados degradados del panel de workers.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import { useAuthStore } from '../../../auth/store'

const api = vi.hoisted(() => ({
  checkServiceDependencies: vi.fn(), deleteServiceLogs: vi.fn(), installServiceDependencies: vi.fn(),
  listAdminServices: vi.fn(), panicStopServices: vi.fn(), serviceHealth: vi.fn(), serviceLogs: vi.fn(),
  serviceLogStream: vi.fn(), setServiceAutoStart: vi.fn(), startAdminService: vi.fn(), stopAdminService: vi.fn(),
}))
const auditApi = vi.hoisted(() => ({ getCatalogAuditSummary: vi.fn() }))
vi.mock('../../../services/adminServices', () => api)
vi.mock('../../catalog-audit/api/catalogAudit', () => auditApi)

import WorkersView from './WorkersView.vue'

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.isAuthenticated = true
  auth.role = 'admin'
  auth.user = { id: 1, identifier: 'admin', role: 'admin' }
  return mount(WorkersView, { global: { plugins: [pinia, vuetify] } })
}

describe('WorkersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    api.listAdminServices.mockResolvedValue([{
      id: 12,
      name: 'catalog_audit_worker',
      status: 'degraded',
      auto_start: true,
      uptime_s: 0,
      last_error: 'El consumidor activo pertenece a otro worktree',
      runtime_mode: 'local',
      pid: 29576,
      runtime_root: 'C:\\Proyectos\\NiceGrow\\Growen-worktrees\\auditor-catalogo-autonomo',
      detail: 'El consumidor activo pertenece a otro worktree',
    }])
    api.serviceHealth.mockResolvedValue({ ok: true })
    api.serviceLogs.mockResolvedValue([])
    auditApi.getCatalogAuditSummary.mockResolvedValue({
      worker: { status: 'degraded', ok: false, broker_ok: true, ready: 2, delayed: 1 },
      runs: { total: 3, active: 2, by_status: { queued: 1, running: 1 }, recent: [] },
      items: { by_status: { pending: 4, auditing: 1 } },
      catalog_coverage: { total_canonical: 29, audited: 20, pending: 9, quarantined: 0 },
    })
  })

  it('expone el origen local y bloquea el inicio de un runtime ajeno', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('local')
    expect(wrapper.text()).toContain('PID 29576')

    await wrapper.find('.v-expansion-panel-title').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('auditor-catalogo-autonomo')
    expect(wrapper.text()).toContain('otro worktree')
    expect(wrapper.findAll('button').some((button) => button.text().trim() === 'Iniciar')).toBe(false)
    expect(api.startAdminService).not.toHaveBeenCalled()
  })

  it('muestra la carga encolada y en curso del auditor', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.v-expansion-panel-title').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('2 listos en Redis')
    expect(wrapper.text()).toContain('1 run encolado')
    expect(wrapper.text()).toContain('1 run en curso')
    expect(wrapper.text()).toContain('4 ítems pendientes')
  })
})
