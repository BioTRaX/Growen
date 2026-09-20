// NG-HEADER: Nombre de archivo: registry.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/registry.spec.ts
// NG-HEADER: Descripción: Pruebas de navegación agrupada y permisos del shell Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { describe, expect, it } from 'vitest'
import { navigationFor, navigationItemsFor } from './registry'

describe('registro de navegación', () => {
  it('agrupa Catálogo y Stock para clientes sin exponer Imágenes', () => {
    const products = navigationFor('cliente').find((entry) => entry.kind === 'group' && entry.title === 'Productos')
    expect(products?.kind).toBe('group')
    if (products?.kind !== 'group') throw new Error('Falta el grupo Productos')
    expect(products.children.map((item) => item.to)).toEqual(['/productos', '/stock'])
  })

  it('expone Imágenes de Productos sólo a staff', () => {
    expect(navigationItemsFor('admin').map((item) => item.to)).toContain('/imagenes-productos')
    expect(navigationItemsFor('proveedor').map((item) => item.to)).not.toContain('/imagenes-productos')
  })

  it('expone sólo el Chat público a invitados', () => {
    const navigation = navigationFor('guest')
    expect(navigation).toHaveLength(1)
    expect(navigation[0]).toMatchObject({ kind: 'item', to: '/chat' })
  })
})
