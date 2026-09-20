// NG-HEADER: Nombre de archivo: http.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/http.ts
// NG-HEADER: Descripción: Cliente HTTP compartido con cookies, CSRF, errores y telemetría de requests.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import axios, { type AxiosError } from 'axios'

export interface RequestDiagnostic {
  at: string
  method: string
  url: string
  status: number
  durationMs: number
  correlationId?: string
  release: string
}

const diagnostics: RequestDiagnostic[] = []
const maxDiagnostics = 100

export function normalizeApiBase(value?: string): string {
  const configured = value?.trim()
  if (!configured) return '/api'
  if (configured.startsWith('/')) return configured.replace(/\/$/, '') || '/api'
  try {
    return new URL(configured).toString().replace(/\/$/, '')
  } catch {
    return '/api'
  }
}

export const apiBaseUrl = normalizeApiBase(import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL)
export const frontendRelease = import.meta.env.VITE_RELEASE || 'local'

function getCookie(name: string): string | undefined {
  const prefix = `${name}=`
  return document.cookie.split('; ').find((part) => part.startsWith(prefix))?.slice(prefix.length)
}

export const http = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  timeout: Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS || 30000),
})

http.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrf = getCookie('csrf_token')
    if (csrf) config.headers.set('X-CSRF-Token', decodeURIComponent(csrf))
  }
  config.headers.set('X-Frontend-Release', frontendRelease)
  ;(config as typeof config & { startedAt?: number }).startedAt = performance.now()
  return config
})

http.interceptors.response.use(
  (response) => {
    recordDiagnostic(response.config, response.status, response.headers['x-correlation-id'])
    return response
  },
  (error: AxiosError) => {
    recordDiagnostic(error.config, error.response?.status ?? 0, error.response?.headers?.['x-correlation-id'] as string | undefined)
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('growen:unauthorized'))
    }
    return Promise.reject(error)
  },
)

function recordDiagnostic(config: AxiosError['config'], status: number, correlationId?: string): void {
  if (!config) return
  const startedAt = (config as typeof config & { startedAt?: number }).startedAt ?? performance.now()
  diagnostics.unshift({
    at: new Date().toISOString(),
    method: (config.method ?? 'get').toUpperCase(),
    url: `${config.baseURL ?? ''}${config.url ?? ''}`,
    status,
    durationMs: Math.max(0, Math.round(performance.now() - startedAt)),
    correlationId,
    release: frontendRelease,
  })
  diagnostics.splice(maxDiagnostics)
}

export function requestDiagnostics(): readonly RequestDiagnostic[] {
  return diagnostics
}

export type HttpErrorKind = 'cancelled' | 'unauthorized' | 'forbidden' | 'conflict' | 'rate_limited' | 'validation' | 'server' | 'network' | 'unknown'

export function classifyHttpError(error: unknown): HttpErrorKind {
  if (axios.isCancel(error) || (error as AxiosError).code === 'ERR_CANCELED') return 'cancelled'
  const status = (error as AxiosError).response?.status
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 409) return 'conflict'
  if (status === 429) return 'rate_limited'
  if (status === 422) return 'validation'
  if (status && status >= 500) return 'server'
  if (!(error as AxiosError).response) return 'network'
  return 'unknown'
}

export function getHttpErrorMessage(error: unknown, fallback = 'No se pudo completar la operación'): string {
  const axiosError = error as AxiosError<{ detail?: string | { message?: string } | Array<{ msg?: string; loc?: unknown[] }>; message?: string }>
  const detail = axiosError.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item.msg).filter(Boolean)
    if (messages.length) return messages.join('. ')
  }
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') return detail.message
  if (typeof axiosError.response?.data?.message === 'string') return axiosError.response.data.message
  if (classifyHttpError(error) === 'cancelled') return ''
  return fallback
}
