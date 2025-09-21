// NG-HEADER: Nombre de archivo: HealthPanel.tsx
// NG-HEADER: Ubicación: frontend/src/components/HealthPanel.tsx
// NG-HEADER: Descripción: Panel de salud que consulta /health/summary y muestra el estado de servicios.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import http from '../services/http'
import { toolsHealth, type ToolsHealth } from '../services/servicesAdmin'

interface HealthDetails {
  db: { ok: boolean; detail?: string }
  redis: { ok: boolean; detail?: string }
  storage: { ok: boolean; detail?: string; free_bytes?: number; total_bytes?: number }
  dramatiq?: {
    ok: boolean
    broker_ok?: boolean
    queues?: { images?: { exists?: boolean; size?: number } }
    workers?: { count?: number }
  } | { ok: boolean; detail?: string }
  ai_providers: string[]
  optional: Record<string, boolean>
  frontend_built?: boolean
  db_migration?: { current_revision: string | null; scripts: number }
  process?: { uptime_seconds: number; host: string }
}

export default function HealthPanel() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<'ok' | 'degraded' | 'unknown'>('unknown')
  const [details, setDetails] = useState<HealthDetails | null>(null)
  const [tools, setTools] = useState<ToolsHealth | null>(null)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const r = await http.get<{ status: 'ok' | 'degraded'; details: HealthDetails }>(`/health/summary`)
      setStatus(r.data.status)
      setDetails(r.data.details)
      try {
        setTools(await toolsHealth())
      } catch { /* opcional */ }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No se pudo consultar la salud')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  function fmtBytes(n?: number) {
    if (!n && n !== 0) return '—'
    const units = ['B','KB','MB','GB','TB']
    let i = 0
    let v = n
    while (v >= 1024 && i < units.length-1) { v /= 1024; i++ }
    return `${v.toFixed(1)} ${units[i]}`
  }

  function fmtDuration(sec?: number) {
    if (!sec && sec !== 0) return '—'
    const d = Math.floor(sec / 86400)
    const h = Math.floor((sec % 86400) / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = Math.floor(sec % 60)
    const parts = [] as string[]
    if (d) parts.push(`${d}d`)
    if (h) parts.push(`${h}h`)
    if (m) parts.push(`${m}m`)
    if (!d && !h && !m) parts.push(`${s}s`)
    return parts.join(' ')
  }

  const Badge = ({ ok }: { ok: boolean }) => (
    <span style={{
      padding: '2px 6px', borderRadius: 6,
      background: ok ? '#064e3b' : '#7f1d1d',
      color: 'white', fontSize: 12,
    }}>{ok ? 'OK' : 'ERROR'}</span>
  )

  return (
    <div className="card" style={{ padding: 12, marginBottom: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Health</h3>
        <button className="btn" type="button" onClick={refresh} disabled={loading}>Actualizar</button>
      </div>
      {loading && <div>Cargando...</div>}
      {error && <div style={{ color: '#fca5a5' }}>{error}</div>}
      {!loading && details && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div className="card" style={{ padding: 8 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>Base de datos</strong>
              <Badge ok={details.db.ok} />
            </div>
            {details.db.detail && <div style={{ fontSize: 12, opacity: 0.85 }}>{details.db.detail}</div>}
          </div>
          <div className="card" style={{ padding: 8 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>Redis</strong>
              <Badge ok={details.redis.ok} />
            </div>
            {details.redis.detail && <div style={{ fontSize: 12, opacity: 0.85 }}>{details.redis.detail}</div>}
          </div>
          <div className="card" style={{ padding: 8 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>Storage</strong>
              <Badge ok={details.storage.ok} />
            </div>
            <div style={{ fontSize: 12, opacity: 0.9 }}>Libre: {fmtBytes(details.storage.free_bytes)}</div>
            {details.storage.detail && <div style={{ fontSize: 12, opacity: 0.85 }}>{details.storage.detail}</div>}
          </div>
          <div className="card" style={{ padding: 8 }}>
            <div><strong>IA providers</strong></div>
            <div style={{ fontSize: 12 }}>{details.ai_providers?.length ? details.ai_providers.join(', ') : 'Ninguno'}</div>
          </div>

          {/* Dramatiq */}
          {details.dramatiq && (
            <div className="card" style={{ padding: 8 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <strong>Dramatiq</strong>
                <Badge ok={(details.dramatiq as any).ok} />
              </div>
              {('broker_ok' in (details.dramatiq as any)) && (
                <div style={{ fontSize: 12 }}>Broker: {(details.dramatiq as any).broker_ok ? 'OK' : 'ERROR'}</div>
              )}
              {('queues' in (details.dramatiq as any)) && (
                <div style={{ fontSize: 12 }}>Cola images: {((details.dramatiq as any).queues?.images?.size) ?? 0} mensajes</div>
              )}
              {('workers' in (details.dramatiq as any)) && (
                <div style={{ fontSize: 12 }}>Workers: {((details.dramatiq as any).workers?.count) ?? 0}</div>
              )}
              {('detail' in (details.dramatiq as any)) && (
                <div style={{ fontSize: 12, opacity: 0.85 }}>{(details.dramatiq as any).detail}</div>
              )}
            </div>
          )}

          {/* Proceso */}
          {details.process && (
            <div className="card" style={{ padding: 8 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <strong>Proceso</strong>
                <span style={{ fontSize: 12 }}>Host: {details.process.host}</span>
              </div>
              <div style={{ fontSize: 12 }}>Uptime: {fmtDuration(details.process.uptime_seconds)}</div>
            </div>
          )}

          {/* Migraciones y Frontend */}
          <div className="card" style={{ padding: 8 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>Estado build</strong>
              <span style={{ fontSize: 12 }}>Frontend: {details.frontend_built ? 'Compilado' : 'Sin build'}</span>
            </div>
            {details.db_migration && (
              <div style={{ fontSize: 12 }}>
                Mig. actual: {details.db_migration.current_revision || '—'} | scripts: {details.db_migration.scripts}
              </div>
            )}
          </div>
          <div className="card" style={{ padding: 8, gridColumn: '1 / -1' }}>
            <div><strong>Dependencias opcionales</strong></div>
            <ul style={{ columns: 2, fontSize: 12 }}>
              {Object.entries(details.optional).map(([k, v]) => (
                <li key={k}>{k}: <Badge ok={!!v} /></li>
              ))}
            </ul>
          </div>
          {/* Herramientas del sistema */}
          {tools && (
            <div className="card" style={{ padding: 8, gridColumn: '1 / -1' }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <strong>Herramientas (host)</strong>
                <button className="btn" type="button" onClick={async () => { try { setTools(await toolsHealth()) } catch {} }}>
                  Re-chequear
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div className="card" style={{ padding: 8 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>QPDF</strong>
                    <Badge ok={tools.qpdf.ok} />
                  </div>
                  <div style={{ fontSize: 12 }}>Path: {tools.qpdf.path || '—'}</div>
                  <div style={{ fontSize: 12 }}>Versión: {tools.qpdf.version || '—'}</div>
                </div>
                <div className="card" style={{ padding: 8 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>Ghostscript</strong>
                    <Badge ok={tools.ghostscript.ok} />
                  </div>
                  <div style={{ fontSize: 12 }}>Path: {tools.ghostscript.path || '—'}</div>
                  <div style={{ fontSize: 12 }}>Versión: {tools.ghostscript.version || '—'}</div>
                </div>
                <div className="card" style={{ padding: 8 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>Tesseract</strong>
                    <Badge ok={tools.tesseract.ok} />
                  </div>
                  <div style={{ fontSize: 12 }}>Path: {tools.tesseract.path || '—'}</div>
                  <div style={{ fontSize: 12 }}>Versión: {tools.tesseract.version || '—'}</div>
                </div>
                <div className="card" style={{ padding: 8 }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>Playwright / Chromium</strong>
                    <Badge ok={tools.playwright.ok} />
                  </div>
                  <div style={{ fontSize: 12 }}>Paquete: {tools.playwright.package ? 'Instalado' : 'No instalado'}</div>
                  <div style={{ fontSize: 12 }}>Chromium: {tools.playwright.chromium ? 'Instalado' : 'No instalado'}</div>
                  <div style={{ fontSize: 12 }}>Versión: {tools.playwright.version || '—'}</div>
                </div>
              </div>
            </div>
          )}
          <div className="card" style={{ padding: 8, gridColumn: '1 / -1' }}>
            <div><strong>Estado general:</strong> {status.toUpperCase()}</div>
          </div>
        </div>
      )}
    </div>
  )
}
