// NG-HEADER: Nombre de archivo: adminServices.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/adminServices.spec.ts
// NG-HEADER: Descripción: Pruebas de contratos HTTP del corte Vue de servicios administrativos.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { afterEach, describe, expect, it, vi } from 'vitest'

import { http } from './http'
import { checkServiceDependencies, cleanPhysicalLogs, listAdminServices, mcpHealth, previewPhysicalLogCleanup, setServiceAutoStart, startAdminService } from './adminServices'

afterEach(() => vi.restoreAllMocks())

describe('adminServices', () => {
  it('consume el inventario y health MCP con rutas canónicas', async () => {
    const get = vi.spyOn(http, 'get')
      .mockResolvedValueOnce({ data: { items: [{ id: 1, name: 'dramatiq', status: 'running', auto_start: true }] } } as never)
      .mockResolvedValueOnce({ data: { servers: [] } } as never)
    expect((await listAdminServices())[0].name).toBe('dramatiq')
    expect((await mcpHealth()).servers).toEqual([])
    expect(get.mock.calls.map(([url]) => url)).toEqual(['/admin/services', '/admin/mcp/health'])
  })

  it('envía modo, auto-start y dependencias por el cliente CSRF compartido', async () => {
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: { ok: true } } as never)
    const patch = vi.spyOn(http, 'patch').mockResolvedValue({ data: { auto_start: true } } as never)
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: { ok: true } } as never)
    await startAdminService('drive_sync_worker', 'local')
    await setServiceAutoStart('dramatiq', true)
    await checkServiceDependencies('dramatiq')
    expect(post).toHaveBeenCalledWith('/admin/services/drive_sync_worker/start', null, { params: { mode: 'local' } })
    expect(patch).toHaveBeenCalledWith('/admin/services/dramatiq', { auto_start: true })
    expect(get).toHaveBeenCalledWith('/admin/services/dramatiq/deps/check')
  })

  it('previsualiza antes de ejecutar la limpieza física con la misma retención', async () => {
    const plan = { log_root: 'logs', keep_days: 7, target_count: 2, bytes_reclaimable: 10, dev_run_directories: 1, targets: [], protected: [] }
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: plan } as never)
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: { plan, result: { ok: true } } } as never)

    expect((await previewPhysicalLogCleanup(7)).target_count).toBe(2)
    expect((await cleanPhysicalLogs(7)).result.ok).toBe(true)
    expect(get).toHaveBeenCalledWith('/admin/services/logs/cleanup-preview', { params: { keep_days: 7 } })
    expect(post).toHaveBeenCalledWith('/admin/services/logs/cleanup', null, { params: { keep_days: 7 } })
  })
})
