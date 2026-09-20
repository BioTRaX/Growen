// NG-HEADER: Nombre de archivo: salesCustomersManifest.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/salesCustomersManifest.spec.ts
// NG-HEADER: Descripción: Pruebas de activación y rutas Vue de Clientes, Ventas y POS.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { frontendManifest } from './manifest'

describe('migración Vue de Clientes y Ventas', () => {
  it.each(['customers', 'sales'])('activa %s en runtime Vue', (moduleId) => {
    const module = frontendManifest.modules.find((candidate) => candidate.id === moduleId)
    expect(module).toMatchObject({ state: 'active', runtime: 'vue' })
  })

  it('registra listado, POS y detalles sin colisionar rutas', () => {
    const paths = frontendManifest.modules.flatMap((module) => module.routes.map((route) => route.path))
    expect(paths).toEqual(expect.arrayContaining([
      '/clientes', '/clientes/:id', '/ventas', '/ventas/nueva', '/ventas/:id',
    ]))
    expect(paths.indexOf('/ventas/nueva')).toBeLessThan(paths.indexOf('/ventas/:id'))
  })
})
