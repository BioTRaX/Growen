// NG-HEADER: Nombre de archivo: MarketDetailDrawer.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/market/components/MarketDetailDrawer.spec.ts
// NG-HEADER: Descripción: Pruebas del enlace y validación manual de fuentes de Mercado.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { mount } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import { VApp } from 'vuetify/components'
import { defineComponent, nextTick, onMounted, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getProductSources: vi.fn(),
  getMarketHistory: vi.fn(),
  forceDetectMarketSourcePrice: vi.fn(),
  manuallyValidateMarketSource: vi.fn(),
}))
vi.mock('../api/market', async (original) => ({ ...(await original()), ...api }))

import MarketDetailDrawer from './MarketDetailDrawer.vue'

const source = {
  id: 31, knowledge_asset_id: 80, labels: ['market'], capabilities: ['price'], trust_score: 0.7,
  exclude_from_enrichment: false, source_name: 'Competidor', url: 'https://example.com/producto', currency: 'ARS',
  source_type: 'static', last_price: 3700, last_checked_at: null, is_mandatory: false, is_active: false,
  validation_status: 'warning', ars_confirmed: true, argentina_delivery_confirmed: false, last_error_code: null,
  last_error_message: null, created_at: '2026-08-30T00:00:00', updated_at: '2026-08-30T00:00:00',
  origin: 'market_discovery', asset_status: 'pending',
} as const

describe('MarketDetailDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    api.getProductSources.mockResolvedValue({
      product_id: 1, product_name: 'Producto', sale_price: null, market_price_reference: null,
      market_price_updated_at: null, market_price_min: null, market_price_max: null,
      mandatory: [], additional: [], quarantined: [source], archived: [],
    })
    api.getMarketHistory.mockResolvedValue([])
  })

  it('abre la fuente en una pestaña segura y ofrece sus acciones operativas', async () => {
    const Host = defineComponent({
      components: { MarketDetailDrawer, VApp },
      template: '<v-app><MarketDetailDrawer :model-value="open" :product="product" /></v-app>',
      setup: () => {
        const open = ref(false)
        onMounted(async () => { await nextTick(); open.value = true })
        return { open, product: { product_id: 1, preferred_name: 'Producto' } }
      },
    })
    const wrapper = mount(Host, {
      attachTo: document.body,
      global: { plugins: [createVuetify()] },
    })
    await vi.waitFor(() => expect(api.getProductSources).toHaveBeenCalledWith(1))
    await wrapper.vm.$nextTick()

    const link = document.body.querySelector('a[href="https://example.com/producto"]')
    expect(link?.getAttribute('target')).toBe('_blank')
    expect(link?.getAttribute('rel')).toContain('noopener')
    expect(document.body.querySelector('[title="Forzar detección de precio"]')).not.toBeNull()
    expect(document.body.querySelector('[title="Validar manualmente"]')).not.toBeNull()

    wrapper.unmount()
  })
})
