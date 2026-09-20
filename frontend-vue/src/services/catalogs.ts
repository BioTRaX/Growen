// NG-HEADER: Nombre de archivo: catalogs.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/catalogs.ts
// NG-HEADER: Descripción: Cliente Vue para generación, historial y descarga de catálogos PDF.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'

export interface CatalogListItem {
  id: string
  filename: string
  size: number
  modified_at: string
  latest: boolean
}

export interface CatalogListResponse {
  items: CatalogListItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export async function generateCatalog(ids: number[]): Promise<void> {
  await http.post('/catalogs/generate', { ids })
}

export async function listCatalogs(params: { page: number; page_size: number; from_dt?: string; to_dt?: string }, signal?: AbortSignal): Promise<CatalogListResponse> {
  return (await http.get<CatalogListResponse>('/catalogs', { params, signal })).data
}

export async function deleteCatalog(id: string): Promise<void> {
  await http.delete(`/catalogs/${id}`)
}
