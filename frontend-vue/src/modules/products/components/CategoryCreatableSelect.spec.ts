// NG-HEADER: Nombre de archivo: CategoryCreatableSelect.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CategoryCreatableSelect.spec.ts
// NG-HEADER: Descripción: Pruebas Vuetify reales de escritura y alta inline de categorías planas.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const createProductCategory = vi.hoisted(() => vi.fn())
vi.mock('../api/products', () => ({ createProductCategory }))

import CategoryCreatableSelect from './CategoryCreatableSelect.vue'

const categories = [
  { id: 1, name: 'Cultivo', parent_id: null, kind: 'category' as const, path: 'Cultivo' },
  { id: 2, name: 'Sustratos', parent_id: 1, kind: 'subcategory' as const, path: 'Sustratos' },
]

describe('CategoryCreatableSelect con Vuetify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.stubGlobal('visualViewport', {
      width: 1024,
      height: 768,
      offsetLeft: 0,
      offsetTop: 0,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
  })
  afterEach(() => document.body.replaceChildren())

  it('acepta escritura, muestra Agregar y selecciona la categoría creada', async () => {
    createProductCategory.mockResolvedValue({ id: 3, name: 'Fertilizantes', parent_id: null, kind: 'category', path: 'Fertilizantes' })
    const wrapper = mount(CategoryCreatableSelect, {
      attachTo: document.body,
      props: { modelValue: null, categories, label: 'Categoría', kind: 'category' },
      global: { plugins: [vuetify] },
    })

    const input = wrapper.get('input')
    await input.trigger('focus')
    await input.setValue('Fertilizantes')
    await flushPromises()
    const option = [...document.body.querySelectorAll('.v-list-item')]
      .find((element) => element.textContent?.includes('Agregar')) as HTMLElement
    expect(option?.textContent).toContain('Fertilizantes')
    option.click()
    await flushPromises()

    expect(createProductCategory).toHaveBeenCalledWith('Fertilizantes', 'category')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([3])
  })

  it('permite el mismo nombre en tipos distintos sin ofrecer duplicados dentro del tipo', async () => {
    const wrapper = mount(CategoryCreatableSelect, {
      attachTo: document.body,
      props: { modelValue: null, categories, label: 'Subcategoría', kind: 'subcategory' },
      global: { plugins: [vuetify] },
    })
    const input = wrapper.get('input')
    await input.trigger('focus')
    await input.setValue('Sustratos')
    await flushPromises()
    expect(document.body.textContent).not.toContain('Agregar “Sustratos”')
    expect(document.body.textContent).toContain('Sustratos')
  })
})
