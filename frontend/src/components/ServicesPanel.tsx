// NG-HEADER: Nombre de archivo: ServicesPanel.tsx
// NG-HEADER: Ubicación: frontend/src/components/ServicesPanel.tsx
// NG-HEADER: Descripción: Panel simple de control de servicios on-demand
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useMemo, useState } from 'react'
import { listServices, startService, stopService, tailServiceLogs, panicStop, healthService, setAutoStart, openLogsStream, ServiceItem, ServiceLogItem, checkDeps, installDeps } from '../services/servicesAdmin'

const SERVICE_LABELS: Record<string, string> = {
  pdf_import: 'Importador PDF (OCR)',
  playwright: 'Playwright / Chromium (crawler)',
  image_processing: 'Procesado de imágenes',
  dramatiq: 'Dramatiq / Redis',
  scheduler: 'Scheduler (03:00 AR)',
  tiendanube: 'Tiendanube',
  notifier: 'Notificaciones (Telegram/Email)'
}

export default function ServicesPanel() {
  const [items, setItems] = useState<ServiceItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [logs, setLogs] = useState<Record<string, ServiceLogItem[]>>({})
  const [live, setLive] = useState<Record<string, boolean>>({})
  const streams = useMemo(() => new Map<string, EventSource>(), [])
  const [err, setErr] = useState<string | null>(null)
  const [health, setHealth] = useState<Record<string, { ok: boolean; hints?: string[] }>>({})

  function Dot({ status }: { status: string }) {
    const color = status === 'running' ? '#22c55e' : (status === 'degraded' || status === 'starting') ? '#f59e0b' : '#ef4444'
    return <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: color, marginRight: 6 }} />
  }

  function truncate(s?: string, n = 80) {
    if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
  }
  function formatUptime(u?: number | null) {
    if (!u || u <= 0) return '—'
    const h = Math.floor(u / 3600)
    const m = Math.floor((u % 3600) / 60)
    const s = u % 60
    const pad = (x: number) => String(x).padStart(2, '0')
    return `${pad(h)}:${pad(m)}:${pad(s)}`
  }

  async function refresh() {
    try {
      setErr(null)
      const s = await listServices()
      setItems(s)
      // fetch health in background
      Promise.all(s.map(async it => {
        try {
          const h = await healthService(it.name)
          setHealth(prev => ({ ...prev, [it.name]: { ok: !!h.ok, hints: h.hints || [] } }))
        } catch {}
      })).catch(() => {})
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'No se pudo obtener servicios')
    }
  }

  useEffect(() => { refresh() }, [])
  // Soft polling to keep status fresh
  useEffect(() => {
    const id = setInterval(() => { refresh() }, 12000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => a.name.localeCompare(b.name))
  }, [items])

  // Cleanup live streams on unmount
  useEffect(() => {
    return () => {
      Array.from(streams.values()).forEach(es => { try { es.close() } catch {} })
      streams.clear()
    }
  }, [streams])

  async function doStart(name: string) {
    setBusy(name)
    try {
      await startService(name)
      await refresh()
      const tl = await tailServiceLogs(name, 50)
      setLogs((prev) => ({ ...prev, [name]: tl }))
    } catch (e: any) {
      setErr(e?.response?.data?.detail || `No se pudo iniciar ${name}`)
    } finally {
      setBusy(null)
    }
  }

  async function doStop(name: string) {
    setBusy(name)
    try {
      await stopService(name)
      await refresh()
      const tl = await tailServiceLogs(name, 50)
      setLogs((prev) => ({ ...prev, [name]: tl }))
    } catch (e: any) {
      setErr(e?.response?.data?.detail || `No se pudo detener ${name}`)
    } finally {
      setBusy(null)
    }
  }

  function toggleLive(name: string) {
    const on = !live[name]
    setLive((prev) => ({ ...prev, [name]: on }))
    try {
      const existing = streams.get(name)
      if (existing) { existing.close(); streams.delete(name) }
      if (on) {
        const last = (logs[name] || []).slice(-1)[0] as any
        const es = openLogsStream(name, (last && (last as any).id) ? (last as any).id : 0)
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data)
            setLogs((prev) => ({ ...prev, [name]: [...(prev[name] || []), data].slice(-200) }))
          } catch {}
        }
        es.onerror = () => { /* keep quiet */ }
        streams.set(name, es)
      }
    } catch {}
  }

  return (
    <div>
      {err && <div style={{ color: '#fca5a5', marginBottom: 8 }}>{err}</div>}
      <div className="row" style={{ gap: 8, marginBottom: 8 }}>
        <button className="btn" onClick={refresh}>Actualizar</button>
        <button
          className="btn-danger"
          onClick={async () => {
            if (!window.confirm('¿Seguro que querés apagar los servicios no esenciales?')) return
            try { await panicStop(); await refresh() } catch (e: any) { setErr(e?.response?.data?.detail || 'No se pudo ejecutar Pánico') }
          }}
        >Pánico: apagar no esenciales</button>
      </div>
      <div className="col" style={{ gap: 10 }}>
        {sorted.map((s) => (
          <div key={s.id} className="row" style={{ alignItems: 'center', gap: 8, flexWrap: 'wrap', border: '1px solid #2a2a2a', borderRadius: 6, padding: 8 }}>
          <div style={{ minWidth: 320 }}>
            <div className="row" style={{ alignItems: 'center' }}>
              <Dot status={s.status} />
              <strong>{SERVICE_LABELS[s.name] || s.name}</strong>
            </div>
            <div style={{ fontSize: 12, color: '#a3a3a3' }} title={s.started_at ? `Inicio: ${s.started_at}` : undefined}>
              estado: {s.status}{s.last_error ? ` · err: ${s.last_error.slice(0, 80)}` : ''}
              {s.uptime_s ? ` · uptime: ${formatUptime(s.uptime_s)}` : ''}
              {health[s.name] && (
                <>
                  {' '}· salud: <span style={{ color: health[s.name].ok ? '#22c55e' : '#ef4444' }}>{health[s.name].ok ? 'OK' : 'FALLA'}</span>
                </>
              )}
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>
              uptime: {Math.max(0, Math.floor((s.uptime_s || 0))) }s{ (s as any).start_ms ? ` · inicio_ms: ${(s as any).start_ms}` : ''}
            </div>
          </div>
          <div className="row" style={{ gap: 6 }}>
              {s.status !== 'running' ? (
                <button className="btn-primary" disabled={busy === s.name} onClick={() => doStart(s.name)}>
                  {busy === s.name ? 'Iniciando...' : 'Iniciar'}
                </button>
              ) : (
                <button className="btn" disabled={busy === s.name} onClick={() => doStop(s.name)}>
                  {busy === s.name ? 'Deteniendo...' : 'Detener'}
                </button>
              )}
            </div>
            <div className="row" style={{ gap: 8, alignItems: 'center', marginTop: 6 }}>
              <label className="text-sm"><input type="checkbox" checked={s.auto_start} onChange={async (e) => { try { await setAutoStart(s.name, e.target.checked); await refresh() } catch {} }} /> Inicio automático</label>
            </div>
            <div style={{ flex: 1 }}>
              <details>
                <summary>Logs recientes</summary>
                <ul style={{ maxHeight: 240, overflow: 'auto', fontSize: 12, lineHeight: 1.35 }}>
                  {(logs[s.name] || []).map((l, i) => {
                    const level = (l.level || '').toUpperCase()
                    const color = level === 'ERROR' ? '#ef4444' : level === 'WARN' || level === 'WARNING' ? '#f59e0b' : '#9ca3af'
                    const msg = l.error || l.payload?.detail || ''
                    return (
                      <li key={i} style={{ color, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        [{l.level}] {l.created_at} · {l.action} · {l.ok ? 'OK' : 'FAIL'}
                        {msg ? ` · ${msg}` : ''}
                      </li>
                    )
                  })}
                </ul>
                <button className="btn" onClick={async () => { const tl = await tailServiceLogs(s.name, 200); setLogs((prev) => ({ ...prev, [s.name]: tl })) }}>Actualizar logs</button>
                <label style={{ marginLeft: 8, opacity: (logs[s.name]?.length || 0) === 0 ? 0.6 : 1 }} title={(logs[s.name]?.length || 0) === 0 ? 'Cargar logs primero' : 'Conectar para ver en vivo'}>
                  <input type="checkbox" checked={!!live[s.name]} disabled={(logs[s.name]?.length || 0) === 0} onChange={() => toggleLive(s.name)} /> En vivo
                </label>
                <button className="btn" style={{ marginLeft: 8 }} onClick={async () => { try { const h = await healthService(s.name); setHealth(prev => ({ ...prev, [s.name]: { ok: !!h.ok, hints: h.hints || [] } })) } catch {} }}>Reintentar health</button>
                <button className="btn" style={{ marginLeft: 8 }} onClick={async () => { try {
                  const r = await checkDeps(s.name)
                  const missing = (r.missing || []).join(', ')
                  alert(`Deps ${s.name}: ${r.ok ? 'OK' : 'FALTAN'}${missing ? `\nFaltan: ${missing}` : ''}`)
                } catch (e: any) { alert(e?.response?.data?.detail || 'Fallo al validar deps') } }}>Validar deps</button>
                <button className="btn" style={{ marginLeft: 8 }} onClick={async () => { try {
                  const r = await installDeps(s.name)
                  const lines = (r.detail || []).slice(0, 12).join('\n')
                  alert((r.disabled ? 'Instalación deshabilitada' : (r.ok ? 'Instalación OK' : 'Instalación falló')) + (lines ? `\n---\n${lines}` : ''))
                  try { const tl = await tailServiceLogs(s.name, 120); setLogs((prev) => ({ ...prev, [s.name]: tl })) } catch {}
                } catch (e: any) { alert(e?.response?.data?.detail || 'Fallo al instalar deps') } }}>Instalar deps</button>
              </details>
              {health[s.name] && health[s.name].hints && health[s.name].hints!.length > 0 && (
                <div className="text-sm" style={{ marginTop: 6, color: '#fbbf24' }}>
                  Hints: {health[s.name].hints!.slice(0, 2).join(' · ')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
