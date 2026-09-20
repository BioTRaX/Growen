// NG-HEADER: Nombre de archivo: TagCreatableSelect.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/TagCreatableSelect.spec.ts
// NG-HEADER: Descripción: Prueba Vuetify real de búsqueda y creación de tags múltiples.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const listProductTags = vi.hoisted(() => vi.fn())
const createProductTag = vi.hoisted(() => vi.fn())
vi.mock('../api/products', () => ({ listProductTags, createProductTag }))

import TagCreatableSelect from './TagCreatableSelect.vue'

describe('TagCreatableSelect con Vuetify', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    listProductTags.mockResolvedValue([])
    createProductTag.mockResolvedValue({ id: 4, name: 'Interior' })
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    vi.stubGlobal('visualViewport', {
      width: 1024, height: 768, offsetLeft: 0, offsetTop: 0,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    })
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.replaceChildren()
  })

  it('busca con debounce y crea una opción inexistente', async () => {
    const wrapper = mount(TagCreatableSelect, {
      attachTo: document.body,
      props: { modelValue: [] },
      global: { plugins: [vuetify] },
    })
    await flushPromises()
    const input = wrapper.get('input')
    await input.trigger('focus')
    await input.setValue('Interior')
    await vi.runAllTimersAsync()
    await flushPromises()
    const option = [...document.body.querySelectorAll('.v-list-item')]
      .find((element) => element.textContent?.includes('Agregar')) as HTMLElement
    expect(option?.textContent).toContain('Interior')
    option.click()
    await flushPromises()
    expect(createProductTag).toHaveBeenCalledWith('Interior')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([['Interior']])
  })
})
