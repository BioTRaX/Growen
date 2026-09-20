// NG-HEADER: Nombre de archivo: capabilities.ts
// NG-HEADER: Ubicación: frontend-vue/src/auth/capabilities.ts
// NG-HEADER: Descripción: Capacidades de UI derivadas de roles; el backend conserva la autorización final.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import type { Capability } from '../app/modules/manifest'
import type { Role } from './types'

const collaborator = new Set<Capability>([
  'services.control',
  'images.review',
  'images.process',
  'chat.review',
])

const administrator = new Set<Capability>([
  ...collaborator,
  'users.manage',
  'backups.manage',
  'services.dependencies.install',
  'images.jobs.read',
  'images.jobs.manage',
  'drive.manage',
  'catalogs.unlock',
  'knowledge.manage',
  'scheduler.manage',
  'chat.prompts.manage',
])

export function capabilitiesForRole(role: Role): ReadonlySet<Capability> {
  if (role === 'admin') return administrator
  if (role === 'colaborador') return collaborator
  return new Set<Capability>()
}

export function hasCapabilities(role: Role, required: Capability[]): boolean {
  const available = capabilitiesForRole(role)
  return required.every((capability) => available.has(capability))
}
