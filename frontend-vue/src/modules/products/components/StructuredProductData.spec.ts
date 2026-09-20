// NG-HEADER: Nombre de archivo: StructuredProductData.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/StructuredProductData.spec.ts
// NG-HEADER: Descripción: Verifica el formato legible de especificaciones e instrucciones estructuradas.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StructuredProductData from './StructuredProductData.vue'

describe('StructuredProductData', () => {
  it('presenta objetos, booleanos y estructuras anidadas sin JSON crudo', () => {
    const wrapper = mount(StructuredProductData, {
      props: {
        value: {
          use: 'Interior y exterior',
          reusable: true,
          capacity_l: 20,
          dimensions_alternative: {
            height_cm: 28,
            source_note: 'Medidas reportadas por otra fuente',
            diameter_top_cm: 32,
          },
        },
      },
    })

    expect(wrapper.text()).toContain('Uso')
    expect(wrapper.text()).toContain('Interior y exterior')
    expect(wrapper.text()).toContain('Reutilizable')
    expect(wrapper.text()).toContain('Sí')
    expect(wrapper.text()).toContain('Capacidad (L)')
    expect(wrapper.text()).toContain('Dimensiones alternativas')
    expect(wrapper.text()).toContain('Diámetro superior (cm)')
    expect(wrapper.text()).not.toContain('{')
    expect(wrapper.text()).not.toContain('"use"')
    expect(wrapper.text()).not.toContain('Source note')
    expect(wrapper.text()).not.toContain('otra fuente')
  })

  it('presenta pasos como lista navegable', () => {
    const wrapper = mount(StructuredProductData, {
      props: { value: { steps: ['Llenar con sustrato.', 'Trasplantar y regar.'] } },
    })

    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.text()).toContain('Llenar con sustrato.')
  })
})
