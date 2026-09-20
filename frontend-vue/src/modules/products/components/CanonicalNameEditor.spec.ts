// NG-HEADER: Nombre de archivo: CanonicalNameEditor.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CanonicalNameEditor.spec.ts
// NG-HEADER: Descripción: Verifica la edición de nombres canónicos y nombres inicialmente ausentes.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const updateCanonicalName = vi.hoisted(() => vi.fn())
const updateProductTitle = vi.hoisted(() => vi.fn())
vi.mock('../api/products', () => ({ updateCanonicalName, updateProductTitle }))

import CanonicalNameEditor from './CanonicalNameEditor.vue'

describe('CanonicalNameEditor', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('permite completar un nombre inicialmente nulo y emite el valor confirmado', async () => {
    updateCanonicalName.mockResolvedValue({ id: 8, name: 'Maceta 20L' })
    const wrapper = mount(CanonicalNameEditor, {
      props: { canonicalProductId: 8, name: null, editable: true },
      global: { plugins: [vuetify] },
    })

    expect(wrapper.text()).toContain('Sin nombre')
    await wrapper.get('[aria-label="Editar nombre canónico"]').trigger('click')
    await wrapper.get('input').setValue('  Maceta 20L  ')
    await wrapper.get('[aria-label="Confirmar nombre"]').trigger('click')
    await flushPromises()

    expect(updateCanonicalName).toHaveBeenCalledWith(8, 'Maceta 20L')
    expect(wrapper.emitted('saved')).toEqual([['Maceta 20L']])
    expect(wrapper.text()).toContain('Maceta 20L')
  })
})
