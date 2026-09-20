// NG-HEADER: Nombre de archivo: ProductDescriptionDialog.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/ProductDescriptionDialog.spec.ts
// NG-HEADER: Descripción: Pruebas unitarias para el diálogo de edición manual de descripción de productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'

const updateCanonicalDescription = vi.hoisted(() => vi.fn())
const updateProductDescription = vi.hoisted(() => vi.fn())
vi.mock('../api/products', () => ({ updateCanonicalDescription, updateProductDescription }))

import ProductDescriptionDialog from './ProductDescriptionDialog.vue'
import { formatDescriptionToHtml } from '../productDescription'

describe('ProductDescriptionDialog', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('formatDescriptionToHtml helper', () => {
    it('convierte texto vacío o espacios a cadena vacía', () => {
      expect(formatDescriptionToHtml('')).toBe('')
      expect(formatDescriptionToHtml('   \n  ')).toBe('')
    })

    it('formatea texto plano con párrafos a etiquetas <p>', () => {
      const input = 'Primer párrafo\n\nSegundo párrafo'
      expect(formatDescriptionToHtml(input)).toBe('<p>Primer párrafo</p><p>Segundo párrafo</p>')
    })

    it('preserva HTML preexistente', () => {
      const html = '<p>Párrafo con <strong>negrita</strong></p>'
      expect(formatDescriptionToHtml(html)).toBe(html)
    })
  })

  it('guarda descripción canónica y emite resultado con revisión incrementada', async () => {
    updateCanonicalDescription.mockResolvedValue({
      id: 20,
      description_html: '<p>Nueva descripción</p>',
      content_revision: 2,
    })

    const wrapper = mount(ProductDescriptionDialog, {
      props: {
        modelValue: true,
        canonicalProductId: 20,
        productId: 30,
        descriptionHtml: '<p>Descripción anterior</p>',
        productTitle: 'Fumanchu 79mm',
      },
      global: { plugins: [vuetify], stubs: { VDialog: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('Editar descripción')
    expect(wrapper.text()).toContain('Fumanchu 79mm')

    const textarea = wrapper.get('textarea')
    await textarea.setValue('Nueva descripción')

    const saveBtn = wrapper.findAll('button').find((btn) => btn.text().includes('Guardar descripción'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(updateCanonicalDescription).toHaveBeenCalledWith(20, '<p>Nueva descripción</p>')
    expect(wrapper.emitted('saved')).toEqual([[{
      descriptionHtml: '<p>Nueva descripción</p>',
      contentRevision: 2,
    }]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('guarda descripción directa en producto sin canónico', async () => {
    updateProductDescription.mockResolvedValue({
      status: 'ok',
      description_html: '<p>Descripción directa</p>',
    })

    const wrapper = mount(ProductDescriptionDialog, {
      props: {
        modelValue: true,
        canonicalProductId: null,
        productId: 35,
        descriptionHtml: '',
        productTitle: 'Producto sin canónico',
      },
      global: { plugins: [vuetify], stubs: { VDialog: { template: '<div><slot /></div>' } } },
    })

    const textarea = wrapper.get('textarea')
    await textarea.setValue('Descripción directa')

    const saveBtn = wrapper.findAll('button').find((btn) => btn.text().includes('Guardar descripción'))
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(updateProductDescription).toHaveBeenCalledWith(35, '<p>Descripción directa</p>')
    expect(wrapper.emitted('saved')).toEqual([[{
      descriptionHtml: '<p>Descripción directa</p>',
      contentRevision: undefined,
    }]])
  })
})
