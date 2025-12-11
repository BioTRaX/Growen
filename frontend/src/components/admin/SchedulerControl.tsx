// NG-HEADER: Nombre de archivo: SchedulerControl.tsx
// NG-HEADER: Ubicación: frontend/src/components/admin/SchedulerControl.tsx
// NG-HEADER: Descripción: Panel de control del scheduler de actualización de precios de mercado
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useState, useEffect } from 'react'

interface SchedulerStatus {
  running: boolean
  enabled: boolean
  working: boolean
  cron_schedule: string
  start_hour: string
  interval_hours: number
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
  const [startHour, setStartHour] = useState<string>('02:00')
  const [intervalHours, setIntervalHours] = useState<number>(24)
  const [configLoading, setConfigLoading] = useState(false)

  const fetchStatus = async () => {
    try {
      const response = await fetch('/admin/scheduler/status', { credentials: 'include' })
      if (!response.ok) {
        // Manejo específico de errores HTTP
        if (response.status === 403) {
          throw new Error('No tienes permisos de administrador para acceder al scheduler. Se requiere rol "admin".')
        } else if (response.status === 404) {
          throw new Error('Endpoint no encontrado. Verifica que el backend esté corriendo y que el router esté registrado.')
        } else if (response.status >= 500) {
          throw new Error(`Error del servidor (${response.status}). Verifica los logs del backend.`)
        } else {
          const errorText = await response.text()
          let errorMessage = `HTTP ${response.status}: ${response.statusText}`
          try {
            const errorData = JSON.parse(errorText)
            if (errorData.detail) errorMessage = errorData.detail
          } catch {
            if (errorText) errorMessage = errorText
          }
          throw new Error(errorMessage)
        }
      }
      const data = await response.json()
      setStatus(data)
      // Sincronizar estado local con configuración del servidor
      if (data.start_hour) setStartHour(data.start_hour)
      if (data.interval_hours) setIntervalHours(data.interval_hours)
      setError(null)
    } catch (err: any) {
      // Detectar errores de red
      if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        setError('Error de conexión. Verifica que el backend esté corriendo y accesible.')
      } else {
        setError(err.message || 'Error al cargar estado del scheduler')
      }
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

  const handleToggle = async () => {
    setActionLoading(true)
    try {
      const response = await fetch('/admin/scheduler/toggle', {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      await fetchStatus()
      setLastResult(null)
    } catch (err: any) {
      setError('Error al alternar scheduler: ' + err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleUpdateConfig = async () => {
    // Validar formato de hora
    const hourRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/
    if (!hourRegex.test(startHour)) {
      setError('Formato de hora inválido. Use HH:MM (ej: 02:00)')
      return
    }
    
    if (intervalHours < 1 || intervalHours > 24) {
      setError('Intervalo debe estar entre 1 y 24 horas')
      return
    }

    setConfigLoading(true)
    try {
      const response = await fetch('/admin/scheduler/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          start_hour: startHour,
          interval_hours: intervalHours,
        }),
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }
      await fetchStatus()
      setError(null)
    } catch (err: any) {
      setError('Error al actualizar configuración: ' + err.message)
    } finally {
      setConfigLoading(false)
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
        {error && (
          <div style={{ 
            padding: 12, 
            marginBottom: 12, 
            backgroundColor: 'var(--danger)', 
            color: 'white', 
            borderRadius: 4 
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}
        {!error && (
          <p style={{ color: 'var(--muted)' }}>Cargando estado del scheduler...</p>
        )}
        <div style={{ marginTop: 12 }}>
          <button 
            className="btn-primary" 
            onClick={fetchStatus}
            disabled={loading}
          >
            🔄 Reintentar
          </button>
        </div>
        {error && error.includes('permisos') && (
          <div style={{ 
            marginTop: 12, 
            padding: 12, 
            backgroundColor: 'var(--bg-secondary)', 
            borderRadius: 4,
            fontSize: 14 
          }}>
            <strong>Nota:</strong> El panel de scheduler requiere rol de administrador. 
            Si necesitas acceso, contacta a un administrador del sistema.
          </div>
        )}
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
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
          {status.working ? (
            <span style={{
              padding: '4px 12px',
              borderRadius: 4,
              backgroundColor: '#f59e0b',
              color: 'white',
              fontWeight: 'bold',
            }}>
              ⚙️ Working
            </span>
          ) : status.running ? (
            <span style={{
              padding: '4px 12px',
              borderRadius: 4,
              backgroundColor: 'var(--success)',
              color: 'white',
              fontWeight: 'bold',
            }}>
              ▶ Running
            </span>
          ) : (
            <span style={{
              padding: '4px 12px',
              borderRadius: 4,
              backgroundColor: 'var(--muted)',
              color: 'white',
              fontWeight: 'bold',
            }}>
              ⏸ OFF
            </span>
          )}
          <span style={{ color: 'var(--muted)' }}>
            {status.enabled ? 'Habilitado' : 'Deshabilitado'}
          </span>
        </div>
        
        {/* Toggle Switch */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={status.running}
              onChange={handleToggle}
              disabled={actionLoading || status.working}
              style={{ width: 40, height: 20, cursor: 'pointer' }}
            />
            <span>Activar/Desactivar Scheduler</span>
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <strong>Cron Schedule:</strong> {status.cron_schedule}
        </div>
        <div style={{ marginBottom: 12 }}>
          <strong>Próxima Ejecución:</strong> {formatNextRun(status.next_run_time)}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            className="btn"
            onClick={fetchStatus}
            disabled={actionLoading}
          >
            🔄 Refrescar
          </button>
        </div>
      </div>

      {/* Configuración */}
      <div style={{ marginBottom: 24 }}>
        <h4>Configuración</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 'bold' }}>
              Hora de Inicio (GMT-3, Argentina)
            </label>
            <input
              type="time"
              value={startHour}
              onChange={(e) => setStartHour(e.target.value)}
              style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid var(--border)' }}
              disabled={configLoading}
            />
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
              Formato: HH:MM (ej: 02:00)
            </div>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 'bold' }}>
              Intervalo (horas)
            </label>
            <input
              type="number"
              min="1"
              max="24"
              value={intervalHours}
              onChange={(e) => setIntervalHours(parseInt(e.target.value) || 24)}
              style={{ width: '100%', padding: 8, borderRadius: 4, border: '1px solid var(--border)' }}
              disabled={configLoading}
            />
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
              Rango: 1-24 horas
            </div>
          </div>
        </div>
        <button
          className="btn-primary"
          onClick={handleUpdateConfig}
          disabled={configLoading || actionLoading}
        >
          {configLoading ? 'Guardando...' : 'Guardar Configuración'}
        </button>
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
