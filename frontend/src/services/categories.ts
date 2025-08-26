export interface Category { id: number; name: string }
import { baseURL as base } from './http'

export async function listCategories(): Promise<Category[]> {
  const res = await fetch(`${base}/categories`, { credentials: 'include' })
  if (!res.ok) throw new Error('Error de red')
  return res.json()
}
