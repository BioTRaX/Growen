// NG-HEADER: Nombre de archivo: SupplierDetailView.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/suppliers/views/SupplierDetailView.spec.ts
// NG-HEADER: Descripción: Pruebas unitarias para la vista de detalle de proveedor con Vuetify.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import { useAuthStore } from '../../../auth/store'
import SupplierDetailView from './SupplierDetailView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '12' } }),
}))

vi.mock('../../../services/suppliers', () => ({
  getSupplier: vi.fn().mockResolvedValue({
    id: 12,
    slug: 'santaplanta',
    name: 'Santa Planta',
    location: 'Buenos Aires',
    contact_name: 'Juan Perez',
    contact_email: 'juan@santaplanta.com',
    contact_phone: '1122334455',
    notes: 'Distribuidor mayorista oficial',
  }),
  listSupplierFiles: vi.fn().mockResolvedValue([
    {
      id: 1,
      filename: 'sha_catalogo.pdf',
      original_name: 'catalogo_2026.pdf',
      uploaded_at: '2026-09-01T12:00:00Z',
      size_bytes: 204800,
      sha256: 'abc123sha',
      processed: true,
      dry_run: false,
      rows: 150,
    },
  ]),
  updateSupplier: vi.fn(),
  uploadSupplierFile: vi.fn(),
}))

vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
})

describe('SupplierDetailView', () => {
  beforeEach(() => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.role = 'admin'
    auth.isAuthenticated = true
  })

  it('muestra la información del proveedor y el listado de archivos', async () => {
    const wrapper = mount(SupplierDetailView, {
      global: { plugins: [vuetify] },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Proveedor: Santa Planta')
    expect(wrapper.text()).toContain('Datos identificatorios')
    expect(wrapper.text()).toContain('catalogo_2026.pdf')
    expect(wrapper.text()).toContain('Descargar')

    const inputs = wrapper.findAll('input').map((i) => (i.element as HTMLInputElement).value)
    expect(inputs).toContain('santaplanta')
    expect(inputs).toContain('Juan Perez')
  })

  it('permite alternar el modo edición y muestra los botones de guardar y cancelar', async () => {
    const wrapper = mount(SupplierDetailView, {
      global: { plugins: [vuetify] },
    })

    await flushPromises()

    const editBtn = wrapper.findAll('button').find((b) => b.text().includes('Editar'))
    expect(editBtn).toBeDefined()

    await editBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Guardar cambios')
    expect(wrapper.text()).toContain('Cancelar')

    const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('Cancelar'))
    await cancelBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Editar')
    expect(wrapper.text()).not.toContain('Guardar cambios')
  })
})
