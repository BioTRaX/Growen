export interface Category { id: number; name: string }

const base = import.meta.env.VITE_API_URL as string

export async function listCategories(): Promise<Category[]> {
  const res = await fetch(`${base}/categories`, { credentials: 'include' })
  if (!res.ok) throw new Error('Error de red')
  return res.json()
}
