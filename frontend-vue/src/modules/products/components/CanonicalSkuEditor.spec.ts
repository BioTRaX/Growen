// NG-HEADER: Nombre de archivo: CanonicalSkuEditor.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CanonicalSkuEditor.spec.ts
// NG-HEADER: Descripción: Prueba la confirmación explícita y colisiones del editor de SKU.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const updateCanonicalSku = vi.hoisted(() => vi.fn())
vi.mock('../api/products', () => ({ updateCanonicalSku }))

import CanonicalSkuEditor from './CanonicalSkuEditor.vue'

function mountEditor() {
  return mount(CanonicalSkuEditor, {
    props: {
      canonicalProductId: 8,
      sku: 'OLD_0001_SKU',
      fallbackSku: 'INTERNO-1',
      editable: true,
    },
    global: { plugins: [vuetify] },
  })
}

describe('CanonicalSkuEditor', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('mantiene el editor abierto y no aplica cuando el SKU ya existe', async () => {
    updateCanonicalSku.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: { code: 'duplicate_sku', message: 'El SKU ya existe. Ingrese uno diferente.' } },
      },
    })
    const wrapper = mountEditor()

    await wrapper.get('[aria-label="Editar SKU"]').trigger('click')
    const input = wrapper.get('input')
    await input.setValue('abc_0001_def')
    await wrapper.get('[aria-label="Confirmar SKU"]').trigger('click')
    await flushPromises()

    expect(updateCanonicalSku).toHaveBeenCalledWith(8, 'ABC_0001_DEF')
    expect(wrapper.text()).toContain('El SKU ya existe. Ingrese uno diferente.')
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.emitted('saved')).toBeUndefined()
  })

  it('aplica sólo al confirmar y emite el SKU normalizado', async () => {
    updateCanonicalSku.mockResolvedValue({ id: 8, sku_custom: 'NEW_0042_A1B' })
    const wrapper = mountEditor()

    await wrapper.get('[aria-label="Editar SKU"]').trigger('click')
    await wrapper.get('input').setValue('new_0042_a1b')
    expect(updateCanonicalSku).not.toHaveBeenCalled()

    await wrapper.get('[aria-label="Confirmar SKU"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toEqual([['NEW_0042_A1B']])
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.text()).toContain('NEW_0042_A1B')
  })
})
