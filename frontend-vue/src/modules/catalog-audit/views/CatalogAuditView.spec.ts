// NG-HEADER: Nombre de archivo: CatalogAuditView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.spec.ts
// NG-HEADER: Descripción: Vista operativa del auditor con Vuetify real.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import CatalogAuditView from './CatalogAuditView.vue'

vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('../api/catalogAudit', () => ({
  listCatalogAudits: vi.fn().mockResolvedValue([]),
  getCatalogAuditPreflight: vi.fn().mockResolvedValue({
    ollama: { ok: true, model: 'llama3.1:8b' }, worker: { ok: true }, enrichment_worker: { ok: true }, queue: 'catalog_audit',
  }),
  createCatalogAudit: vi.fn(), getCatalogAudit: vi.fn(), cancelCatalogAudit: vi.fn(),
  retryCatalogAudit: vi.fn(), resolveCatalogAuditItem: vi.fn(),
}))
vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })

describe('CatalogAuditView', () => {
  it('muestra preflight y permite configurar una ejecución', async () => {
    const wrapper = mount(CatalogAuditView, { global: { plugins: [createPinia(), vuetify] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Auditor autónomo de catálogo')
    expect(wrapper.text()).toContain('llama3.1:8b')
    expect(wrapper.text()).toContain('Worker disponible')
    expect(wrapper.text()).toContain('Iniciar auditoría')
  })
})
