// NG-HEADER: Nombre de archivo: catalogDiagnostics.ts
// NG-HEADER: Ubicación: frontend/src/services/catalogDiagnostics.ts
// NG-HEADER: Descripción: Servicios para endpoints de diagnóstico de catálogos PDF
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { baseURL as base } from './http'

export interface CatalogStatus {
  active_generation: { running: boolean; started_at: string | null; ids: number };
  detail_logs: number;
  summaries: number;
}

export interface CatalogSummaryItem {
  generated_at: string;
  file: string;
  size: number;
  count: number;
  duration_ms: number;
}

export interface CatalogSummariesResponse { items: CatalogSummaryItem[]; total: number }

export interface CatalogDetailLogLine {
  ts?: string;
  step?: string;
  [k: string]: any;
}

export interface CatalogDetailLogResponse { items: CatalogDetailLogLine[]; count: number }

async function handleJson<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    try { const j = await res.json(); throw new Error(j.detail || fallback) } catch {
      throw new Error(fallback)
    }
  }
  return res.json()
}

export async function getCatalogStatus(signal?: AbortSignal): Promise<CatalogStatus> {
  const res = await fetch(base + '/catalogs/diagnostics/status', { credentials: 'include', signal })
  return handleJson<CatalogStatus>(res, 'Error obteniendo estado de catálogos')
}

export async function getCatalogSummaries(limit = 20, signal?: AbortSignal): Promise<CatalogSummariesResponse> {
  const res = await fetch(base + `/catalogs/diagnostics/summaries?limit=${limit}`, { credentials: 'include', signal })
  return handleJson<CatalogSummariesResponse>(res, 'Error obteniendo resúmenes de catálogos')
}

export async function getCatalogDetailLog(id: string, signal?: AbortSignal): Promise<CatalogDetailLogResponse> {
  const res = await fetch(base + `/catalogs/diagnostics/log/${id}`, { credentials: 'include', signal })
  return handleJson<CatalogDetailLogResponse>(res, 'Error obteniendo log detallado')
}
