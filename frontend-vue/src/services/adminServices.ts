// NG-HEADER: Nombre de archivo: adminServices.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/adminServices.ts
// NG-HEADER: Descripción: Cliente tipado para workers, logs, dependencias y servidores MCP del panel admin.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { http } from './http'
import { openEventStream } from './transports'

export type ServiceStatus = 'stopped' | 'starting' | 'running' | 'degraded' | 'failed'

export interface AdminService {
  id: number
  name: string
  status: ServiceStatus
  auto_start: boolean
  started_at?: string | null
  uptime_s?: number | null
  last_error?: string | null
}

export interface ServiceLog {
  id?: number
  created_at?: string | null
  service: string
  action: string
  cid: string
  ok: boolean
  level?: string | null
  error?: string | null
  payload?: Record<string, unknown>
}

export interface McpServer {
  name: string
  label: string
  url: string
  resolved_url?: string | null
  port: number
  status: 'running' | 'stopped' | 'error'
  healthy: boolean
  lastCheck?: string
  error?: string | null
  protocol?: string
  protocol_version?: string
  tool_count?: number
}

export interface LogCleanupPlan {
  log_root: string
  keep_days: number
  target_count: number
  bytes_reclaimable: number
  dev_run_directories: number
  targets: Array<{ path: string; kind: 'file' | 'directory' | 'truncate'; size_bytes: number; reason: string }>
  protected: Array<{ path: string; reason: string }>
}

export interface LogCleanupResult {
  ok: boolean
  removed_files: number
  removed_directories: number
  truncated_files: number
  bytes_reclaimed: number
  errors: Array<{ path: string; error: string }>
}

export const listAdminServices = async () => (await http.get<{ items: AdminService[] }>('/admin/services')).data.items
export const startAdminService = async (name: string, mode?: 'docker' | 'local') =>
  (await http.post(`/admin/services/${encodeURIComponent(name)}/start`, null, { params: mode ? { mode } : undefined })).data
export const stopAdminService = async (name: string) => (await http.post(`/admin/services/${encodeURIComponent(name)}/stop`)).data
export const panicStopServices = async () => (await http.post('/admin/services/panic-stop')).data
export const setServiceAutoStart = async (name: string, autoStart: boolean) =>
  (await http.patch(`/admin/services/${encodeURIComponent(name)}`, { auto_start: autoStart })).data
export const serviceHealth = async (name: string) => (await http.get(`/health/service/${encodeURIComponent(name)}`)).data
export const serviceLogs = async (name: string, tail = 200) =>
  (await http.get<{ items: ServiceLog[] }>(`/admin/services/${encodeURIComponent(name)}/logs`, { params: { tail } })).data.items
export const deleteServiceLogs = async (name: string) => (await http.delete(`/admin/services/${encodeURIComponent(name)}/logs`)).data
export const previewPhysicalLogCleanup = async (keepDays = 7) =>
  (await http.get<LogCleanupPlan>('/admin/services/logs/cleanup-preview', { params: { keep_days: keepDays } })).data
export const cleanPhysicalLogs = async (keepDays = 7) =>
  (await http.post<{ plan: LogCleanupPlan; result: LogCleanupResult }>('/admin/services/logs/cleanup', null, { params: { keep_days: keepDays } })).data
export const checkServiceDependencies = async (name: string) => (await http.get(`/admin/services/${encodeURIComponent(name)}/deps/check`)).data
export const installServiceDependencies = async (name: string) => (await http.post(`/admin/services/${encodeURIComponent(name)}/deps/install`)).data
export const serviceLogStream = (name: string, lastId = 0) =>
  openEventStream(`/admin/services/${encodeURIComponent(name)}/logs/stream${lastId ? `?last_id=${lastId}` : ''}`)

export const mcpHealth = async () => (await http.get<{ servers: McpServer[]; context?: string }>('/admin/mcp/health')).data
export const startMcp = async (name: string) => (await http.post(`/admin/mcp/${encodeURIComponent(name)}/start`)).data
export const stopMcp = async (name: string) => (await http.post(`/admin/mcp/${encodeURIComponent(name)}/stop`)).data
