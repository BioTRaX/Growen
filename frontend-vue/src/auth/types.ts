// NG-HEADER: Nombre de archivo: types.ts
// NG-HEADER: Ubicación: frontend-vue/src/auth/types.ts
// NG-HEADER: Descripción: Contratos de usuario y roles compartidos por autenticación y router.
// NG-HEADER: Lineamientos: Ver AGENTS.md
export const roles = ['guest', 'cliente', 'proveedor', 'colaborador', 'admin'] as const

export type Role = (typeof roles)[number]

export interface User {
  id: number
  identifier: string
  email?: string | null
  name?: string | null
  role: Role
  supplier_id?: number | null
}
