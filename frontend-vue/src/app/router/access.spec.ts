// NG-HEADER: Nombre de archivo: access.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/router/access.spec.ts
// NG-HEADER: Descripción: Pruebas de autorización por rol en rutas Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { describe, expect, it } from 'vitest'

import { resolveRouteAccess } from './access'

describe('resolveRouteAccess', () => {
  it('permite rutas públicas sin lista de roles', () => {
    expect(resolveRouteAccess(undefined, 'guest', false)).toBe('allow')
  })

  it('permite una ruta que admite invitados', () => {
    expect(resolveRouteAccess(['guest', 'admin'], 'guest', false)).toBe('allow')
  })

  it('redirige al login cuando falta autenticación', () => {
    expect(resolveRouteAccess(['colaborador', 'admin'], 'guest', false)).toBe('login')
  })

  it('rechaza un rol autenticado sin permisos', () => {
    expect(resolveRouteAccess(['admin'], 'colaborador', true)).toBe('forbidden')
  })

  it('permite un rol autenticado incluido', () => {
    expect(resolveRouteAccess(['colaborador', 'admin'], 'admin', true)).toBe('allow')
  })

  it('aplica capacidades además del rol', () => {
    expect(resolveRouteAccess(['colaborador', 'admin'], 'colaborador', true, ['users.manage'])).toBe('forbidden')
    expect(resolveRouteAccess(['admin'], 'admin', true, ['users.manage'])).toBe('allow')
  })
})
