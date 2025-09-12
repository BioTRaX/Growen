import http from './http'

export interface ServiceItem {
  id: number
  name: string
  status: 'stopped' | 'starting' | 'running' | 'degraded' | 'failed'
  auto_start: boolean
  started_at?: string | null
  uptime_s?: number | null
  last_error?: string | null
}

export interface ServiceLogItem {
  created_at?: string | null
  service: string
  action: string
  cid: string
  ok: boolean
  level?: string | null
  error?: string | null
  payload?: any
}

export async function listServices(): Promise<ServiceItem[]> {
  const r = await http.get<{ items: ServiceItem[] }>(`/admin/services`)
  return r.data.items
}

export async function serviceStatus(name: string): Promise<{ name: string; status: string; detail?: string }>{
  const r = await http.get(`/admin/services/${encodeURIComponent(name)}/status`)
  return r.data
}

export async function startService(name: string): Promise<{ name: string; status: string; ok: boolean; correlation_id: string; detail?: string }>{
  const r = await http.post(`/admin/services/${encodeURIComponent(name)}/start`)
  return r.data
}

export async function stopService(name: string): Promise<{ name: string; status: string; ok: boolean; correlation_id: string; detail?: string }>{
  const r = await http.post(`/admin/services/${encodeURIComponent(name)}/stop`)
  return r.data
}

export async function panicStop(): Promise<{ stopped: Array<{ name: string; status: string; ok: boolean; correlation_id: string }> }>{
  const r = await http.post(`/admin/services/panic-stop`)
  return r.data
}

export async function tailServiceLogs(name: string, tail = 200): Promise<ServiceLogItem[]> {
  const r = await http.get<{ items: ServiceLogItem[] }>(`/admin/services/${encodeURIComponent(name)}/logs`, { params: { tail } })
  return r.data.items
}

export async function healthService(name: string): Promise<{ ok: boolean; service: string; deps?: any; hints?: string[]; error?: string; version?: string }>{
  const r = await http.get(`/health/service/${encodeURIComponent(name)}`)
  return r.data
}

export async function setAutoStart(name: string, auto_start: boolean): Promise<{ name: string; auto_start: boolean }>{
  const r = await http.patch(`/admin/services/${encodeURIComponent(name)}`, { auto_start })
  return r.data
}

export function openLogsStream(name: string, lastId = 0): EventSource {
  const u = new URL(`/admin/services/${encodeURIComponent(name)}/logs/stream`, window.location.origin)
  if (lastId) u.searchParams.set('last_id', String(lastId))
  return new EventSource(u.toString())
}

// Deps check/install
export async function checkDeps(name: string): Promise<{ ok: boolean; missing?: string[]; detail?: string[]; hints?: string[] }>{
  const r = await http.get(`/admin/services/${encodeURIComponent(name)}/deps/check`)
  return r.data
}

export async function installDeps(name: string): Promise<{ ok: boolean; detail?: string[]; disabled?: boolean; hint?: string }>{
  const r = await http.post(`/admin/services/${encodeURIComponent(name)}/deps/install`)
  return r.data
}
