// NG-HEADER: Nombre de archivo: adminCore.spec.ts
// NG-HEADER: Ubicación: frontend-vue/src/services/adminCore.spec.ts
// NG-HEADER: Descripción: Pruebas de rutas administrativas de usuarios y backups.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http } from './http'
import { createUser, listBackups, listUsers, resetUserPassword, runBackup } from './adminCore'

afterEach(() => vi.restoreAllMocks())

describe('adminCore', () => {
  it('normaliza filtros de usuarios y mutaciones', async () => {
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: [] } as never)
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: { password: 'temporal' } } as never)
    await listUsers('ana', 'admin'); await createUser({ identifier: 'ana', password: 'segura', role: 'admin' }); await resetUserPassword(4)
    expect(get).toHaveBeenCalledWith('/auth/users', { params: { q: 'ana', role: 'admin' } })
    expect(post).toHaveBeenCalledWith('/auth/users', { identifier: 'ana', password: 'segura', role: 'admin' })
    expect(post).toHaveBeenCalledWith('/auth/users/4/reset-password')
  })

  it('consume listado y ejecución de backups', async () => {
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: { items: [{ filename: 'backup.sql', size: 1, modified: '2026-07-17' }] } } as never)
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: { meta: { file: 'backup.sql' } } } as never)
    expect((await listBackups())[0].filename).toBe('backup.sql'); expect((await runBackup()).meta?.file).toBe('backup.sql')
    expect(get).toHaveBeenCalledWith('/admin/backups'); expect(post).toHaveBeenCalledWith('/admin/backups/run')
  })
})
