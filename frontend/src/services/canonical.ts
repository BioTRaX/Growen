export interface CanonicalOffer {
  supplier: { id: number; name: string; slug: string }
  precio_venta: number | null
  precio_compra: number | null
  compra_minima: number | null
  updated_at: string | null
  supplier_product_id: number
  mejor_precio: boolean
}

const base = import.meta.env.VITE_API_URL as string

export async function listOffersByCanonical(
  canonicalId: number,
): Promise<CanonicalOffer[]> {
  const res = await fetch(
    `${base}/canonical-products/${canonicalId}/offers`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
