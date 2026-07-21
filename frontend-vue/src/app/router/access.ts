// NG-HEADER: Nombre de archivo: access.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/router/access.ts
// NG-HEADER: Descripción: Regla pura de autorización para rutas Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import type { Role } from '../../auth/types'
import type { Capability } from '../modules/manifest'
import { hasCapabilities } from '../../auth/capabilities'

export type AccessResult = 'allow' | 'login' | 'forbidden'

export function resolveRouteAccess(
  allowedRoles: Role[] | undefined,
  role: Role,
  isAuthenticated: boolean,
  requiredCapabilities: Capability[] = [],
): AccessResult {
  if (!allowedRoles) return 'allow'
  if (allowedRoles.includes('guest') && role === 'guest') return 'allow'
  if (!isAuthenticated) return 'login'
  return allowedRoles.includes(role) && hasCapabilities(role, requiredCapabilities) ? 'allow' : 'forbidden'
}
