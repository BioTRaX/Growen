// NG-HEADER: Nombre de archivo: ensureServiceRunning.ts
// NG-HEADER: Ubicación: frontend/src/lib/ensureServiceRunning.ts
// NG-HEADER: Descripción: Utilidad para iniciar un servicio y esperar hasta running con poll.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { startService, serviceStatus } from '../services/servicesAdmin'

export async function ensureServiceRunning(name: string, opts?: { timeoutMs?: number; intervalMs?: number }) {
  const timeoutMs = opts?.timeoutMs ?? 60_000
  const intervalMs = opts?.intervalMs ?? 1500
  // Intento idempotente de start (será NOOP si ya estaba running/starting)
  try { await startService(name) } catch { /* ignore start errors; we will poll status */ }
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const st = await serviceStatus(name)
      const s = (st?.status || '').toLowerCase()
      if (s === 'running') return st
      // starting/degraded: seguir esperando un poco, salvo que ya no quede tiempo
    } catch {
      // si status falla, esperamos y reintentamos
    }
    await new Promise(r => setTimeout(r, intervalMs))
  }
  throw new Error('timeout esperando que el servicio esté running')
}

