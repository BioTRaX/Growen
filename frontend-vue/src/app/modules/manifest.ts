// NG-HEADER: Nombre de archivo: manifest.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/modules/manifest.ts
// NG-HEADER: Descripción: Contrato tipado y validación del manifiesto único de módulos frontend.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import rawManifest from '../../../generated/modules.runtime.json'
import type { Role } from '../../auth/types'

export type MigrationState = 'pending' | 'partial' | 'ready' | 'active'
export type ModuleRuntime = 'legacy' | 'vue'
export type Capability =
  | 'users.manage'
  | 'backups.manage'
  | 'services.control'
  | 'services.dependencies.install'
  | 'images.review'
  | 'images.process'
  | 'images.jobs.read'
  | 'images.jobs.manage'
  | 'drive.manage'
  | 'catalogs.unlock'
  | 'knowledge.manage'
  | 'scheduler.manage'
  | 'chat.review'
  | 'chat.prompts.manage'

export interface ModuleRoute {
  path: string
  name: string
  title: string
  component: string
  roles: Role[]
  capabilities?: Capability[]
  navigation?: boolean
}

export interface FrontendModule {
  id: string
  title: string
  icon: string
  group: string
  roles: Role[]
  capabilities: Capability[]
  state: MigrationState
  runtime: ModuleRuntime
  routes: ModuleRoute[]
  aliases: string[]
}

export interface FrontendManifest {
  version: number
  modules: FrontendModule[]
}

const knownRoles = new Set<Role>(['guest', 'cliente', 'proveedor', 'colaborador', 'admin'])

export function validateManifest(value: FrontendManifest): FrontendManifest {
  if (value.version !== 1 || !Array.isArray(value.modules)) throw new Error('Manifiesto frontend inválido')
  const ids = new Set<string>()
  const routeNames = new Set<string>()
  for (const module of value.modules) {
    if (!module.id || ids.has(module.id)) throw new Error(`ID de módulo duplicado o vacío: ${module.id}`)
    ids.add(module.id)
    if (module.runtime === 'vue' && module.state !== 'active') {
      throw new Error(`El módulo ${module.id} usa Vue sin estar active`)
    }
    if (!module.routes.length || module.roles.some((role) => !knownRoles.has(role))) {
      throw new Error(`Roles o rutas inválidos en ${module.id}`)
    }
    for (const route of module.routes) {
      if (!route.path.startsWith('/') || routeNames.has(route.name)) throw new Error(`Ruta inválida o duplicada: ${route.name}`)
      routeNames.add(route.name)
    }
  }
  return value
}

export const frontendManifest = validateManifest(rawManifest as FrontendManifest)

export function moduleForPath(path: string): FrontendModule | undefined {
  return frontendManifest.modules.find((module) => module.routes.some((route) => {
    if (route.path === '/') return path === '/'
    const pattern = route.path
      .replace(/:[^/]+\(\.\*\)\*/g, '.*')
      .replace(/:[^/]+/g, '[^/]+')
    return new RegExp(`^${pattern}/?$`).test(path)
  }))
}
