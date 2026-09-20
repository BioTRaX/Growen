// NG-HEADER: Nombre de archivo: CatalogAuditView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/catalog-audit/views/CatalogAuditView.spec.ts
// NG-HEADER: Descripción: Vista operativa del auditor con Vuetify real.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { vuetify } from '../../../app/providers/vuetify'
import * as catalogAuditApi from '../api/catalogAudit'
import type { CatalogAuditRun } from '../types'
import CatalogAuditView from './CatalogAuditView.vue'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRoute: () => ({ query: {} }) }
})
vi.mock('../api/catalogAudit', () => ({
  listCatalogAudits: vi.fn().mockResolvedValue([]),
  getCatalogAuditPreflight: vi.fn().mockResolvedValue({
    ollama: { ok: true, model: 'llama3.1:8b' }, worker: { ok: true }, enrichment_worker: { ok: true }, queue: 'catalog_audit',
  }),
  createCatalogAudit: vi.fn(), getCatalogAudit: vi.fn(), cancelCatalogAudit: vi.fn(),
  retryCatalogAudit: vi.fn(), resolveCatalogAuditItem: vi.fn(),
}))
vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/productos/:id', component: { template: '<div />' } },
    ],
  })
  return mount(CatalogAuditView, { global: { plugins: [createPinia(), vuetify, router] } })
}

describe('CatalogAuditView', () => {
  it('muestra preflight y permite configurar una ejecución', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Auditor autónomo de catálogo')
    expect(wrapper.text()).toContain('llama3.1:8b')
    expect(wrapper.text()).toContain('Worker disponible')
    expect(wrapper.text()).toContain('Iniciar auditoría')
  })

  it('permite reanudar una ejecución completada con ítems fallidos', async () => {
    const run: CatalogAuditRun = {
      run_id: 'run-con-fallos', scope: 'all', mode: 'full', status: 'completed_with_issues',
      include_orphans: true, enrich_missing: true, auto_fix: false,
      total_items: 29, processed_items: 29, clean_items: 28, issue_items: 1,
      cancel_requested: false,
      items: [{
        item_id: 32, canonical_product_id: 29, product_id: null, status: 'failed',
        canonical_name: 'Producto con error', product_detail_id: null,
        input_hash: 'hash', rules_version: 'rules-v1', feedback_version: 'feedback-v1',
        product_class: null, score: null, passed: false, corrections: [], evidence: [],
        content_versions: [], error: { code: 'invalid_json' },
      }],
    }
    vi.mocked(catalogAuditApi.listCatalogAudits).mockResolvedValueOnce([run]).mockResolvedValueOnce([run])
    vi.mocked(catalogAuditApi.getCatalogAudit).mockResolvedValue(run)
    vi.mocked(catalogAuditApi.retryCatalogAudit).mockResolvedValue(undefined)

    const wrapper = mountView()
    await flushPromises()

    const retryButton = wrapper.findAll('button').find((button) => button.text().includes('Reanudar fallidos'))
    expect(retryButton).toBeDefined()
    await retryButton!.trigger('click')
    await flushPromises()
    expect(catalogAuditApi.retryCatalogAudit).toHaveBeenCalledWith(run.run_id)
  })

  it('muestra el nombre canónico y abre únicamente la ficha interna vinculada', async () => {
    const run: CatalogAuditRun = {
      run_id: 'run-identidad', scope: 'all', mode: 'deterministic_only', status: 'completed_with_issues',
      include_orphans: true, enrich_missing: false, auto_fix: false,
      total_items: 2, processed_items: 2, clean_items: 1, issue_items: 1,
      cancel_requested: false,
      items: [
        {
          item_id: 41, canonical_product_id: 29, product_id: null,
          canonical_name: 'Maceta Soplada 20L', product_detail_id: 17, status: 'clean',
          input_hash: 'hash-1', rules_version: 'rules-v1', feedback_version: 'feedback-v1',
          product_class: 'container', score: 98, passed: true, corrections: [], evidence: [], content_versions: [],
        },
        {
          item_id: 42, canonical_product_id: 30, product_id: null,
          canonical_name: 'Canónico sin ficha', product_detail_id: null, status: 'needs_review',
          input_hash: 'hash-2', rules_version: 'rules-v1', feedback_version: 'feedback-v1',
          product_class: null, score: 70, passed: false, corrections: [], evidence: [], content_versions: [],
        },
      ],
    }
    vi.mocked(catalogAuditApi.listCatalogAudits).mockResolvedValueOnce([run])
    vi.mocked(catalogAuditApi.getCatalogAudit).mockResolvedValue(run)

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Maceta Soplada 20L')
    expect(wrapper.text()).toContain('Canónico #29')
    expect(wrapper.text()).toContain('Sin ficha interna vinculada')
    const productLink = wrapper.findAll('a').find((link) => link.text().includes('Maceta Soplada 20L'))
    expect(productLink?.attributes('href')).toBe('/productos/17')
    expect(wrapper.find('a[href="/productos/29"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/productos/30"]').exists()).toBe(false)
  })
})
