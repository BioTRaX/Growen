// NG-HEADER: Nombre de archivo: registry.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/registry.ts
// NG-HEADER: Descripción: Registro de navegación modular filtrada por rol.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { frontendManifest, type Capability, type MigrationState, type ModuleRuntime } from './manifest'
import { hasCapabilities } from '../../auth/capabilities'
import type { Role } from '../../auth/types'

export interface NavItem {
  kind: 'item'
  title: string
  icon: string
  to: string
  roles: Role[]
  capabilities: Capability[]
  migrationState: MigrationState
  runtime: ModuleRuntime
}

export interface NavGroup {
  kind: 'group'
  title: string
  icon: string
  roles: Role[]
  children: NavItem[]
}

export type NavEntry = NavItem | NavGroup

const groupIcons: Record<string, string> = {
  Productos: 'mdi-sprout-outline',
  Operaciones: 'mdi-briefcase-outline',
  Administración: 'mdi-cog-outline',
}

const rawItems: Array<NavItem & { group: string }> = frontendManifest.modules.flatMap((module) => {
  const route = module.routes.find((candidate) => candidate.navigation !== false)
  if (!route) return []
  return [{
    kind: 'item',
    title: module.title,
    icon: module.icon,
    to: route.path,
    roles: module.roles,
    capabilities: module.capabilities,
    migrationState: module.state,
    runtime: module.runtime,
    group: module.group,
  }]
})

export const navigation: NavEntry[] = rawItems.reduce<NavEntry[]>((entries, item) => {
  if (item.group === 'Inicio') return [...entries, item]
  const existing = entries.find((entry): entry is NavGroup => entry.kind === 'group' && entry.title === item.group)
  if (existing) {
    existing.children.push(item)
    return entries
  }
  return [...entries, {
    kind: 'group',
    title: item.group,
    icon: groupIcons[item.group] ?? 'mdi-folder-outline',
    roles: item.roles,
    children: [item],
  }]
}, [])

export function navigationFor(role: Role): NavEntry[] {
  return navigation.reduce<NavEntry[]>((entries, entry) => {
    if (entry.kind === 'item') {
      return entry.roles.includes(role) && hasCapabilities(role, entry.capabilities) ? [...entries, entry] : entries
    }
    const children = entry.children.filter((item) => item.roles.includes(role) && hasCapabilities(role, item.capabilities))
    return children.length ? [...entries, { ...entry, roles: [...new Set(children.flatMap((item) => item.roles))], children }] : entries
  }, [])
}

export function navigationItemsFor(role: Role): NavItem[] {
  return navigationFor(role).flatMap((entry) => entry.kind === 'group' ? entry.children : [entry])
}
