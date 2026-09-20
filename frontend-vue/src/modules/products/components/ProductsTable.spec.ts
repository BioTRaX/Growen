// NG-HEADER: Nombre de archivo: ProductsTable.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductsTable.spec.ts
// NG-HEADER: Descripción: Visibilidad y eventos de acciones del listado Vue de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { vuetify } from '../../../app/providers/vuetify'
import type { ProductListItem } from '../types'
import ProductsTable from './ProductsTable.vue'

class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver = ResizeObserverMock

const product: ProductListItem = {
  product_id: 17,
  name: 'Maceta interna',
  preferred_name: 'Maceta Soplada 20L',
  supplier: { id: 3, slug: 'proveedor', name: 'Proveedor' },
  supplier_item_id: 41,
  precio_compra: 100,
  precio_venta: 150,
  canonical_sale_price: 160,
  compra_minima: 1,
  category_id: null,
  subcategory_id: null,
  category_path: null,
  stock: 4,
  updated_at: null,
  canonical_product_id: 29,
  canonical_sku: 'MAC_0029_20L',
  canonical_name: 'Maceta Soplada 20L',
  catalog_audit_status: 'needs_review',
  catalog_audit_run_id: 'run-29',
  catalog_audit_item_id: 32,
  first_variant_sku: null,
  tags: [],
  image_url: null,
  images_count: 0,
  primary_image_id: null,
}

function mountTable(canResolveAudit: boolean) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/productos/:id', component: { template: '<div />' } }],
  })
  return mount(ProductsTable, {
    props: { items: [product], loading: false, canEdit: true, canResolveAudit, selected: [] },
    global: { plugins: [vuetify, router] },
  })
}

describe('ProductsTable', () => {
  it('emite el producto al aceptar una revisión con coordenadas completas', async () => {
    const wrapper = mountTable(true)
    await flushPromises()

    const button = wrapper.findAll('button').find((candidate) => candidate.text().includes('Aceptar revisión'))
    expect(button).toBeDefined()
    await button!.trigger('click')
    expect(wrapper.emitted('acceptAudit')).toEqual([[product]])
  })

  it('oculta la aceptación cuando el rol no puede resolver auditorías', async () => {
    const wrapper = mountTable(false)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Aceptar revisión')
  })

  it('oculta la aceptación si faltan las coordenadas persistidas', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/productos/:id', component: { template: '<div />' } }],
    })
    const wrapper = mount(ProductsTable, {
      props: {
        items: [{ ...product, catalog_audit_item_id: null }],
        loading: false, canEdit: true, canResolveAudit: true, selected: [],
      },
      global: { plugins: [vuetify, router] },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Aceptar revisión')
  })
})
