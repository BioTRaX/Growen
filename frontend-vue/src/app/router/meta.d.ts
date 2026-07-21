// NG-HEADER: Nombre de archivo: meta.d.ts
// NG-HEADER: Ubicación: frontend-vue/src/app/router/meta.d.ts
// NG-HEADER: Descripción: Metadatos tipados de rutas Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import 'vue-router'
import type { Role } from '../../auth/types'
import type { Capability } from '../modules/manifest'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    roles?: Role[]
    capabilities?: Capability[]
    moduleId?: string
    runtime?: 'legacy' | 'vue'
    public?: boolean
    migrationPending?: boolean
  }
}
