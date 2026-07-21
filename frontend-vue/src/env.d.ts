// NG-HEADER: Nombre de archivo: env.d.ts
// NG-HEADER: Ubicación: frontend-vue/src/env.d.ts
// NG-HEADER: Descripción: Tipos del entorno Vite y de componentes Vue.
// NG-HEADER: Lineamientos: Ver AGENTS.md
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_URL?: string
  readonly VITE_RELEASE?: string
  readonly VITE_REQUEST_TIMEOUT_MS?: string
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}
