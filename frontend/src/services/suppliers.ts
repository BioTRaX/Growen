export interface Supplier {
  id: number
  name: string
  slug: string
}

const base = import.meta.env.VITE_API_URL as string

export async function listSuppliers(): Promise<Supplier[]> {
  const r = await fetch(`${base}/suppliers`, { credentials: 'include' })
  if (!r.ok) throw new Error('Error de red')
  return r.json()
}

export async function createSupplier(payload: { name: string; slug: string }): Promise<Supplier> {
  const r = await fetch(`${base}/suppliers`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (r.status === 409) throw new Error('slug existente')
  if (!r.ok) throw new Error('datos inválidos')
  return r.json()
}
