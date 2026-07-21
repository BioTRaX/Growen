// NG-HEADER: Nombre de archivo: manifest.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/manifest.spec.ts
// NG-HEADER: Descripción: Pruebas del manifiesto único y selección de runtime frontend.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { frontendManifest, moduleForPath, validateManifest, type FrontendManifest } from './manifest'

describe('manifiesto frontend', () => {
  it('cubre rutas y aliases relevantes y activa Vue sÃ³lo con estado active', () => {
    expect(moduleForPath('/productos/42')?.id).toBe('products')
    expect(frontendManifest.modules.find((module) => module.id === 'images')?.aliases).toEqual([
      '/admin/imagenes',
      '/admin/imagenes-productos',
    ])
    expect(frontendManifest.modules
      .filter((module) => module.runtime === 'vue')
      .every((module) => module.state === 'active')).toBe(true)
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
