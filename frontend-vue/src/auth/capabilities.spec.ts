// NG-HEADER: Nombre de archivo: capabilities.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/auth/capabilities.spec.ts
// NG-HEADER: Descripción: Pruebas de capacidades visibles por rol en la UI Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { hasCapabilities } from './capabilities'

describe('capacidades por rol', () => {
  it('reserva usuarios, backups y jobs administrativos para admin', () => {
    expect(hasCapabilities('colaborador', ['users.manage'])).toBe(false)
    expect(hasCapabilities('colaborador', ['backups.manage'])).toBe(false)
    expect(hasCapabilities('admin', ['users.manage', 'backups.manage', 'images.jobs.manage'])).toBe(true)
  })

  it('permite operación colaborativa explícita', () => {
    expect(hasCapabilities('colaborador', ['services.control', 'images.review'])).toBe(true)
    expect(hasCapabilities('proveedor', ['images.review'])).toBe(false)
  })
})
