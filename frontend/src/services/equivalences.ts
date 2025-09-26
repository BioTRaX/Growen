// NG-HEADER: Nombre de archivo: equivalences.ts
// NG-HEADER: Ubicación: frontend/src/services/equivalences.ts
// NG-HEADER: Descripción: Servicios HTTP para equivalencias de productos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
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
