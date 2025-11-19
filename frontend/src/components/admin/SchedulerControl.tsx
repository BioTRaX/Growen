// NG-HEADER: Nombre de archivo: SchedulerControl.tsx
// NG-HEADER: Ubicación: frontend/src/components/admin/SchedulerControl.tsx
// NG-HEADER: Descripción: Panel de control del scheduler de actualización de precios de mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useState, useEffect } from 'react'

interface SchedulerStatus {
  running: boolean
  enabled: boolean
  cron_schedule: string
  next_run_time: string | null
  update_frequency_days: number
  max_products_per_run: number
  prioritize_mandatory: boolean
  stats: {
    total_products_with_sources: number
    never_updated: number
    outdated: number
    pending_update: number
    total_sources: number
  }
}

interface ManualRunResult {
  success: boolean
  message: string
  products_enqueued: number
  sources_total: number
  duration_seconds: number
}

export default function SchedulerControl() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [lastResult, setLastResult] = useState<ManualRunResult | null>(null)
  const [maxProducts, setMaxProducts] = useState<number>(50)
  const [daysThreshold, setDaysThreshold] = useState<number>(2)

  const fetchStatus = async () => {
    try {
      const response = await fetch('/admin/scheduler/status', { credentials: 'include' })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const data = await response.json()
      setStatus(data)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Error al cargar estado')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // Refrescar cada 30s
    return () => clearInterval(interval)
  }, [])

  const handleStart = async () => {
    setActionLoading(true)
    try {
      const response = await fetch('/admin/scheduler/start', {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      await fetchStatus()
      setLastResult(null)
    } catch (err: any) {
      setError('Error al iniciar scheduler: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleStop = async () => {
    setActionLoading(true)
    try {
      const response = await fetch('/admin/scheduler/stop', {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      await fetchStatus()
      setLastResult(null)
    } catch (err: any) {
      setError('Error al detener scheduler: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleRunNow = async () => {
    setActionLoading(true)
    setLastResult(null)
    try {
      const response = await fetch('/admin/scheduler/run-now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          max_products: maxProducts,
          days_threshold: daysThreshold,
        }),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const result = await response.json()
      setLastResult(result)
      await fetchStatus()
    } catch (err: any) {
      setError('Error al ejecutar manualmente: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const formatNextRun = (nextRun: string | null): string => {
    if (!nextRun) return 'No programado'
    const date = new Date(nextRun)
    const now = new Date()
    const diff = date.getTime() - now.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    if (hours > 24) return `En ${Math.floor(hours / 24)} días`
    if (hours > 0) return `En ${hours}h ${minutes}m`
    if (minutes > 0) return `En ${minutes} minutos`
    return 'Muy pronto'
  }

  if (loading) {
    return (
      <div className="card" style={{ padding: 12 }}>
        <h3>Scheduler de Actualización de Mercado</h3>
        <p>Cargando...</p>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="card" style={{ padding: 12 }}>
        <h3>Scheduler de Actualización de Mercado</h3>
        <p style={{ color: 'red' }}>Error: No se pudo cargar el estado del scheduler</p>
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: 12 }}>
      <h3>Scheduler de Actualización de Mercado</h3>

      {error && (
        <div style={{ padding: 12, marginBottom: 12, backgroundColor: 'var(--danger)', color: 'white', borderRadius: 4 }}>
          {error}
        </div>
      )}

      {/* Estado del Scheduler */}
      <div style={{ marginBottom: 24 }}>
        <h4>Estado</h4>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
          <span style={{
            padding: '4px 12px',
            borderRadius: 4,
            backgroundColor: status.running ? 'var(--success)' : 'var(--muted)',
            color: 'white',
            fontWeight: 'bold',
          }}>
            {status.running ? '▶ Running' : '⏸ Stopped'}
          </span>
          <span style={{ color: 'var(--muted)' }}>
            {status.enabled ? 'Habilitado' : 'Deshabilitado'}
          </span>
        </div>

        <div style={{ marginBottom: 8 }}>
          <strong>Cron Schedule:</strong> {status.cron_schedule}
        </div>
        <div style={{ marginBottom: 12 }}>
          <strong>Próxima Ejecución:</strong> {formatNextRun(status.next_run_time)}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn-primary"
            onClick={handleStart}
            disabled={status.running || actionLoading}
          >
            ▶ Iniciar
          </button>
          <button
            className="btn-secondary"
            onClick={handleStop}
            disabled={!status.running || actionLoading}
          >
            ⏸ Detener
          </button>
          <button
            className="btn"
            onClick={fetchStatus}
            disabled={actionLoading}
          >
            🔄 Refrescar
          </button>
        </div>
      </div>

      {/* Configuración Actual */}
      <div style={{ marginBottom: 24 }}>
        <h4>Configuración Actual</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <strong>Frecuencia de actualización:</strong> {status.update_frequency_days} días
          </div>
          <div>
            <strong>Máx. productos por ejecución:</strong> {status.max_products_per_run}
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <strong>Priorizar obligatorias:</strong> {status.prioritize_mandatory ? 'Sí' : 'No'}
          </div>
        </div>
      </div>

      {/* Estadísticas */}
      <div style={{ marginBottom: 24 }}>
        <h4>Estadísticas</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div style={{ padding: 12, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--primary)' }}>
              {status.stats.total_products_with_sources}
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>Productos con fuentes</div>
          </div>
          <div style={{ padding: 12, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--warning)' }}>
              {status.stats.pending_update}
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>Pendientes de actualizar</div>
          </div>
          <div style={{ padding: 12, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: 'var(--danger)' }}>
              {status.stats.never_updated}
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>Nunca actualizados</div>
          </div>
          <div style={{ padding: 12, backgroundColor: 'var(--bg-secondary)', borderRadius: 4 }}>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>
              {status.stats.total_sources}
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 14 }}>Fuentes totales</div>
          </div>
        </div>
      </div>

      {/* Ejecución Manual */}
      <div>
        <h4>Ejecución Manual</h4>
        <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 12 }}>
          Ejecutar actualización inmediata con parámetros personalizados
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>
              Máximo productos (1-500)
            </label>
            <input
              type="number"
              min="1"
              max="500"
              value={maxProducts}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMaxProducts(parseInt(e.target.value) || 50)}
              style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid var(--border)' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>
              Días desde última actualización (0-365)
            </label>
            <input
              type="number"
              min="0"
              max="365"
              value={daysThreshold}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDaysThreshold(parseInt(e.target.value) || 2)}
              style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid var(--border)' }}
            />
          </div>
        </div>
        <button
          className="btn-primary"
          onClick={handleRunNow}
          disabled={actionLoading}
        >
          ▶ Ejecutar Ahora
        </button>

        {lastResult && (
          <div style={{
            marginTop: 12,
            padding: 12,
            backgroundColor: lastResult.success ? 'var(--success-light)' : 'var(--danger-light)',
            borderRadius: 4,
          }}>
            <strong>{lastResult.success ? '✓ Éxito' : '✗ Error'}</strong>
            <div>{lastResult.message}</div>
            {lastResult.success && (
              <div style={{ marginTop: 8, fontSize: 14 }}>
                <div>• Productos encolados: {lastResult.products_enqueued}</div>
                <div>• Fuentes totales: {lastResult.sources_total}</div>
                <div>• Duración: {lastResult.duration_seconds.toFixed(2)}s</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
