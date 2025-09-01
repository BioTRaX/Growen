// NG-HEADER: Nombre de archivo: categories.ts
// NG-HEADER: Ubicación: frontend/src/services/categories.ts
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
export interface Category { id: number; name: string }
import { baseURL as base } from './http'

export async function listCategories(): Promise<Category[]> {
  const res = await fetch(`${base}/categories`, { credentials: 'include' })
  if (!res.ok) throw new Error('Error de red')
  return res.json()
}
