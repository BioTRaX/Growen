import http from './http'

export interface EquivalenceRequest {
  supplier_id: number
  supplier_product_id: number
  canonical_product_id: number
  source?: string
  confidence?: number | null
}

export async function upsertEquivalence(req: EquivalenceRequest): Promise<any> {
  const res = await http.post('/equivalences', {
    ...req,
    source: req.source ?? 'manual',
  })
  return res.data
}
