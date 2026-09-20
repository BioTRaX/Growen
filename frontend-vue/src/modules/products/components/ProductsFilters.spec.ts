// NG-HEADER: Nombre de archivo: ProductsFilters.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductsFilters.spec.ts
// NG-HEADER: Descripción: Prueba de eventos del formulario de filtros de Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { DEFAULT_PRODUCT_FILTERS } from '../productFilters'
import { vuetify } from '../../../app/providers/vuetify'
import ProductsFilters from './ProductsFilters.vue'

describe('ProductsFilters', () => {
  it('emite cambios de búsqueda sin mutar el modelo recibido', async () => {
    const wrapper = mount(ProductsFilters, {
      props: { modelValue: DEFAULT_PRODUCT_FILTERS, categories: [], suppliers: [] },
      global: { plugins: [vuetify] },
    })
    const field = wrapper.get('input')
    await field.setValue('sustrato')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:modelValue')).toEqual([[{ q: 'sustrato' }]])
    expect(DEFAULT_PRODUCT_FILTERS.q).toBe('')
  })
})
