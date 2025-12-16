// NG-HEADER: Nombre de archivo: DashboardStats.tsx
// NG-HEADER: Ubicación: frontend/src/pages/admin/DashboardStats.tsx
// NG-HEADER: Descripción: Dashboard de estadísticas generales del sistema
// NG-HEADER: Lineamientos: Ver AGENTS.md

import { useEffect, useState } from 'react'
import http from '../../services/http'
import { useToast } from '../../components/ToastProvider'
import { getChatStats } from '../../services/chats'

interface SystemStats {
  health: any
  chat: any
}

export default function DashboardStats() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)
  const { push } = useToast()

  async function loadStats() {
    setLoading(true)
    try {
      const [healthRes, chatRes] = await Promise.all([
        http.get('/health/summary').catch(() => ({ data: null })),
        getChatStats().catch(() => null),
      ])
      setStats({
        health: healthRes.data,
        chat: chatRes,
      })
    } catch (error: any) {
      push({ kind: 'error', title: 'Error', message: error?.response?.data?.detail || 'Error cargando estadísticas' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStats()
    const interval = setInterval(loadStats, 30000) // Refresh cada 30 segundos
    return () => clearInterval(interval)
  }, [])

  if (loading && !stats) {
    return <div style={{ padding: 24, textAlign: 'center' }}>Cargando estadísticas...</div>
  }

  const formatBytes = (bytes: number | null | undefined) => {
    if (!bytes) return 'N/A'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = bytes
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    return `${size.toFixed(2)} ${units[unitIndex]}`
  }

  const formatUptime = (seconds: number | null | undefined) => {
    if (!seconds) return 'N/A'
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (days > 0) return `${days}d ${hours}h`
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Dashboard de Estadísticas</h3>
        <button className="btn" onClick={loadStats} disabled={loading}>
          {loading ? 'Actualizando...' : 'Actualizar'}
        </button>
      </div>

      {/* Sistema */}
      {stats?.health && (
        <div className="panel" style={{ padding: 16 }}>
          <h4 style={{ marginTop: 0 }}>Estado del Sistema</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Estado General</div>
              <div style={{ fontSize: 18, fontWeight: 'bold', color: stats.health.status === 'ok' ? 'var(--success)' : 'var(--error)' }}>
                {stats.health.status === 'ok' ? '✓ Operativo' : '⚠ Degradado'}
              </div>
            </div>
            {stats.health.details?.process && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Uptime</div>
                <div style={{ fontSize: 18, fontWeight: 'bold' }}>
                  {formatUptime(stats.health.details.process.uptime_seconds)}
                </div>
              </div>
            )}
            {stats.health.details?.storage && (
              <div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Espacio Libre</div>
                <div style={{ fontSize: 18, fontWeight: 'bold' }}>
                  {formatBytes(stats.health.details.storage.free_bytes)}
                </div>
              </div>
            )}
          </div>

          {/* Componentes */}
          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {stats.health.details?.db && (
              <div style={{ padding: 8, background: stats.health.details.db.ok ? 'var(--bg-hover)' : 'rgba(244, 67, 54, 0.1)', borderRadius: 4 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Base de Datos</div>
                <div style={{ fontWeight: 'bold', color: stats.health.details.db.ok ? 'var(--success)' : 'var(--error)' }}>
                  {stats.health.details.db.ok ? '✓ OK' : '✗ Error'}
                </div>
              </div>
            )}
            {stats.health.details?.redis && (
              <div style={{ padding: 8, background: stats.health.details.redis.ok ? 'var(--bg-hover)' : 'rgba(244, 67, 54, 0.1)', borderRadius: 4 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Redis</div>
                <div style={{ fontWeight: 'bold', color: stats.health.details.redis.ok ? 'var(--success)' : 'var(--error)' }}>
                  {stats.health.details.redis.ok ? '✓ OK' : '✗ Error'}
                </div>
              </div>
            )}
            {stats.health.details?.dramatiq && (
              <div style={{ padding: 8, background: stats.health.details.dramatiq.ok ? 'var(--bg-hover)' : 'rgba(244, 67, 54, 0.1)', borderRadius: 4 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Workers Dramatiq</div>
                <div style={{ fontWeight: 'bold', color: stats.health.details.dramatiq.ok ? 'var(--success)' : 'var(--error)' }}>
                  {stats.health.details.dramatiq.ok ? `✓ ${stats.health.details.dramatiq.workers?.count || 0} workers` : '✗ Sin workers'}
                </div>
                {stats.health.details.dramatiq.queues && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                    Colas: {Object.entries(stats.health.details.dramatiq.queues)
                      .filter(([_, q]: any) => q.size > 0)
                      .map(([name, q]: any) => `${name}:${q.size}`)
                      .join(', ') || 'vacías'}
                  </div>
                )}
              </div>
            )}
            {stats.health.details?.ai_providers && (
              <div style={{ padding: 8, background: 'var(--bg-hover)', borderRadius: 4 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Proveedores IA</div>
                <div style={{ fontWeight: 'bold' }}>
                  {stats.health.details.ai_providers.length > 0 ? stats.health.details.ai_providers.join(', ') : 'Ninguno'}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Estadísticas de Chat */}
      {stats?.chat && (
        <div className="panel" style={{ padding: 16 }}>
          <h4 style={{ marginTop: 0 }}>Chat</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Total Sesiones</div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.chat.total_sessions || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Total Mensajes</div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.chat.total_messages || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Últimos 7 días</div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.chat.sessions_last_7_days || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Últimos 30 días</div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{stats.chat.sessions_last_30_days || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Promedio Mensajes/Sesión</div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                {stats.chat.avg_messages_per_session ? stats.chat.avg_messages_per_session.toFixed(1) : '0'}
              </div>
            </div>
          </div>
          {stats.chat.sessions_by_status && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Sesiones por Estado</div>
              <div style={{ display: 'flex', gap: 12 }}>
                {Object.entries(stats.chat.sessions_by_status).map(([status, count]: [string, any]) => (
                  <div key={status} style={{ padding: 8, background: 'var(--bg-hover)', borderRadius: 4 }}>
                    <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'capitalize' }}>{status}</div>
                    <div style={{ fontSize: 18, fontWeight: 'bold' }}>{count}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!stats && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>
          No se pudieron cargar las estadísticas
        </div>
      )}
    </div>
  )
}

