// NG-HEADER: Nombre de archivo: manifest.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/manifest.spec.ts
// NG-HEADER: Descripción: Pruebas del manifiesto único y selección de runtime frontend.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { frontendManifest, moduleForPath, validateManifest, type FrontendManifest } from './manifest'

describe('manifiesto frontend', () => {
  it('cubre rutas y aliases relevantes y activa Vue sólo con estado active', () => {
    expect(moduleForPath('/productos')?.id).toBe('products')
    expect(moduleForPath('/productos/42')?.id).toBe('product-detail')
    expect(moduleForPath('/productos/42/Conocimiento')?.id).toBe('product-detail')
    expect(moduleForPath('/productos/42/imagen')?.id).toBe('product-image-legacy')
    expect(frontendManifest.modules.find((module) => module.id === 'images')?.aliases).toEqual([
      '/admin/imagenes',
      '/admin/imagenes-productos',
    ])
    expect(frontendManifest.modules
      .filter((module) => module.runtime === 'vue')
      .every((module) => module.state === 'active')).toBe(true)
  })

  it('activa catálogo y detalle en Vue sin capturar la imagen avanzada legacy', () => {
    const products = frontendManifest.modules.find((module) => module.id === 'products')
    const detail = frontendManifest.modules.find((module) => module.id === 'product-detail')
    const images = frontendManifest.modules.find((module) => module.id === 'product-image-legacy')
    expect(products).toMatchObject({ state: 'active', runtime: 'vue' })
    expect(products?.routes.map((route) => route.path)).toEqual(['/productos'])
    expect(detail).toMatchObject({ state: 'active', runtime: 'vue' })
    expect(detail?.routes.find((route) => route.name === 'product-knowledge')?.roles).toEqual(['colaborador', 'admin'])
    expect(images).toMatchObject({ state: 'partial', runtime: 'legacy' })
  })

  it('activa Stock y Faltantes conjuntamente en Vue', () => {
    const stock = frontendManifest.modules.find((module) => module.id === 'stock')
    expect(stock).toMatchObject({ state: 'active', runtime: 'vue' })
    expect(stock?.routes.map((route) => route.path)).toEqual(['/stock', '/stock/shortages'])
  })

  it('rechaza runtime Vue si el módulo no está active', () => {
    const invalid = structuredClone(frontendManifest) as FrontendManifest
    invalid.modules[0].runtime = 'vue'
    expect(() => validateManifest(invalid)).toThrow(/requiere|sin estar active/)
  })

  it('activa servicios admin sin capturar el resto del panel legacy', () => {
    const services = frontendManifest.modules.find((module) => module.id === 'admin-services')
    const legacy = frontendManifest.modules.find((module) => module.id === 'admin')
    expect(services).toMatchObject({ state: 'active', runtime: 'vue', capabilities: ['services.control'] })
    expect(services?.routes.find((route) => route.name === 'admin-mcp')?.roles).toEqual(['admin'])
    expect(legacy).toMatchObject({ runtime: 'legacy' })
  })
})
