// NG-HEADER: Nombre de archivo: CatalogAuditReviewDialog.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/modules/products/components/CatalogAuditReviewDialog.spec.ts
// NG-HEADER: Descripción: Confirmación administrada de revisiones del auditor desde Productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { vuetify } from '../../../app/providers/vuetify'
import * as catalogAuditApi from '../../catalog-audit/api/catalogAudit'
import type { ProductListItem } from '../types'
import CatalogAuditReviewDialog from './CatalogAuditReviewDialog.vue'

vi.mock('../../catalog-audit/api/catalogAudit', () => ({ resolveCatalogAuditItem: vi.fn() }))
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver = ResizeObserverMock
Object.defineProperty(globalThis, 'visualViewport', {
  configurable: true,
  value: {
    width: 1024, height: 768, offsetLeft: 0, offsetTop: 0,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  },
})

const product: ProductListItem = {
  product_id: 17, name: 'Maceta interna', preferred_name: 'Maceta Soplada 20L',
  supplier: { id: 3, slug: 'proveedor', name: 'Proveedor' }, supplier_item_id: 41,
  precio_compra: 100, precio_venta: 150, canonical_sale_price: 160, compra_minima: 1,
  category_id: null, subcategory_id: null, category_path: null, stock: 4, updated_at: null,
  canonical_product_id: 29, canonical_sku: 'MAC_0029_20L', canonical_name: 'Maceta Soplada 20L',
  catalog_audit_status: 'needs_review', catalog_audit_run_id: 'run-29', catalog_audit_item_id: 32,
  first_variant_sku: null, tags: [], image_url: null, images_count: 0, primary_image_id: null,
}

function mountDialog(productValue: ProductListItem = product) {
  return mount(CatalogAuditReviewDialog, {
    props: { modelValue: true, product: productValue },
    global: { plugins: [vuetify], stubs: { VDialog: { template: '<div><slot /></div>' } } },
  })
}

describe('CatalogAuditReviewDialog', () => {
  beforeEach(() => vi.clearAllMocks())

  it('exige al menos tres caracteres útiles en la nota', async () => {
    const wrapper = mountDialog()
    await wrapper.get('textarea').setValue('  x ')

    const confirm = wrapper.findAll('button').find((button) => button.text().includes('Aceptar revisión'))
    expect(confirm?.attributes('disabled')).toBeDefined()
    expect(catalogAuditApi.resolveCatalogAuditItem).not.toHaveBeenCalled()
  })

  it('acepta la excepción con la nota normalizada y cierra el diálogo', async () => {
    vi.mocked(catalogAuditApi.resolveCatalogAuditItem).mockResolvedValue({ item: {} as never, new_run_id: null })
    const wrapper = mountDialog()
    await wrapper.get('textarea').setValue('  Producto verificado  ')

    const confirm = wrapper.findAll('button').find((button) => button.text().includes('Aceptar revisión'))
    await confirm!.trigger('click')
    await flushPromises()

    expect(catalogAuditApi.resolveCatalogAuditItem).toHaveBeenCalledWith('run-29', 32, {
      action: 'accept_exception', note: 'Producto verificado',
    })
    expect(wrapper.emitted('resolved')).toEqual([[product]])
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('conserva el diálogo abierto y muestra un error si la petición falla', async () => {
    vi.mocked(catalogAuditApi.resolveCatalogAuditItem).mockRejectedValue(new Error('fallo de red'))
    const wrapper = mountDialog()
    await wrapper.get('textarea').setValue('Producto verificado')

    const confirm = wrapper.findAll('button').find((button) => button.text().includes('Aceptar revisión'))
    await confirm!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No se pudo aceptar la revisión')
    expect(wrapper.emitted('resolved')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('rechaza localmente un producto sin coordenadas de auditoría', async () => {
    const wrapper = mountDialog({ ...product, catalog_audit_run_id: null })
    await wrapper.get('textarea').setValue('Producto verificado')

    const confirm = wrapper.findAll('button').find((button) => button.text().includes('Aceptar revisión'))
    await confirm!.trigger('click')
    await flushPromises()

    expect(catalogAuditApi.resolveCatalogAuditItem).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('No se encontraron las coordenadas de la revisión')
  })
})
