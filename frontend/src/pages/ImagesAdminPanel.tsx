// NG-HEADER: Nombre de archivo: ImagesAdminPanel.tsx
// NG-HEADER: UbicaciÃ³n: frontend/src/pages/ImagesAdminPanel.tsx
// NG-HEADER: DescripciÃ³n: Panel de imÃ¡genes con estado, triggers y revisiÃ³n.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import http from '../services/http'
import { Link } from 'react-router-dom'
import { serviceStatus, startService, tailServiceLogs, ServiceLogItem } from '../services/servicesAdmin'

export default function ImagesAdminPanel() {
  const [status, setStatus] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [form, setForm] = useState<any>({ active: false, mode: 'off', retries: 3, rate_rps: 1, burst: 3, log_retention_days: 90, purge_ttl_days: 30 })
  const [scope, setScope] = useState<'stock' | 'all'>('stock')
  const [pendingReview, setPendingReview] = useState<any[]>([])
  const [probe, setProbe] = useState<any | null>(null)
  const [correlationId, setCorrelationId] = useState<string | null>(null)
  const [snapshots, setSnapshots] = useState<any[]>([])
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null)
  const [gatePlayNeeded, setGatePlayNeeded] = useState(false)
  const [gatePlayBusy, setGatePlayBusy] = useState(false)
  const [gatePlayLogs, setGatePlayLogs] = useState<ServiceLogItem[]>([])

  useEffect(() => {
    refresh()
    const id = setInterval(() => { refresh(false) }, 4000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function refresh(showErrors: boolean = true) {
    try {
      const r = await http.get('/admin/image-jobs/status')
      setStatus(r.data)
      setForm((prev: any) => ({ ...prev, active: r.data.active, mode: r.data.mode }))
      const lg = await http.get('/admin/image-jobs/logs', { params: { limit: 50 } })
      const items = Array.isArray(lg.data) ? lg.data : (lg.data.items || [])
  setLogs(items)
      // fetch NDJSON file tail for more detailed crawler events
      try {
        const nd = await http.get('/admin/image-jobs/ndjson-file', { params: { limit: 200 } })
        const lines = (nd.data || "").split('\n').filter(Boolean)
  const pretty = lines.slice(-50).map((l: string) => l)
        setLogs(prev => [...pretty, ...prev].slice(0, 200))
      } catch (e) {
        // ignore
      }
      const rev = await http.get('/products/images/review', { params: { status: 'pending' } })
      setPendingReview(rev.data || [])
    } catch (e) {
      if (showErrors) console.warn('refresh error', e)
    }
  }

  async function fetchSnapshots(cid: string) {
    try {
      const r = await http.get('/admin/image-jobs/snapshots', { params: { correlation_id: cid } })
      setSnapshots(r.data.snapshots || [])
    } catch (e) {
      console.warn('snapshots fetch error', e)
      setSnapshots([])
    }
  }

  async function save() {
    await http.put('/admin/image-jobs/settings', form)
    await refresh()
  }

  async function ensurePlaywright(): Promise<boolean> {
    try {
      const st = await serviceStatus('playwright')
      if ((st?.status || '') !== 'running') {
        setGatePlayNeeded(true)
        try { setGatePlayLogs(await tailServiceLogs('playwright', 80)) } catch {}
        return false
      }
      return true
    } catch {
      return true
    }
  }

  async function startPlaywrightNow() {
    setGatePlayBusy(true)
    try {
      await startService('playwright')
      await new Promise(r => setTimeout(r, 600))
      setGatePlayNeeded(false)
      alert('Playwright iniciado')
    } catch (e) {
      alert('No se pudo iniciar Playwright (ver logs)')
      try { setGatePlayLogs(await tailServiceLogs('playwright', 120)) } catch {}
    } finally {
      setGatePlayBusy(false)
    }
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>ImÃ¡genes productos</h2>
        <Link to="/admin" className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
      </div>
      {gatePlayNeeded && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div className="panel" style={{ padding: 16, minWidth: 460 }}>
            <h4 style={{ marginTop: 0 }}>Crawler apagado</h4>
            <p className="text-sm" style={{ opacity: 0.9 }}>El escaneo necesita el servicio "Playwright / Chromium" encendido. ¿Iniciarlo ahora?</p>
            <div className="row" style={{ gap: 8, marginTop: 6 }}>
              <button className="btn-secondary" onClick={() => setGatePlayNeeded(false)} disabled={gatePlayBusy}>Cancelar</button>
              <button className="btn-primary" onClick={startPlaywrightNow} disabled={gatePlayBusy}>{gatePlayBusy ? 'Iniciando…' : 'Iniciar ahora'}</button>
            </div>
            <details style={{ marginTop: 8 }}>
              <summary>Ver logs recientes</summary>
              <ul style={{ maxHeight: 160, overflow: 'auto', fontSize: 12 }}>
                {gatePlayLogs.map((l, i) => (
                  <li key={i}>[{l.level}] {l.created_at} · {l.action} · {l.ok ? 'OK' : 'FAIL'} · {(l as any).error || (l as any)?.payload?.detail || ''}</li>
                ))}
              </ul>
              <button className="btn" onClick={async () => { try { setGatePlayLogs(await tailServiceLogs('playwright', 120)) } catch {} }}>Actualizar logs</button>
            </details>
          </div>
        </div>
      )}
      <div className="row" style={{ gap: 8, alignItems: 'center' }}>
        <label><input type="checkbox" checked={form.active} onChange={e => setForm({ ...form, active: e.target.checked })} /> Activado</label>
        <select className="select" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
          <option value="off">Off</option>
          <option value="on">On</option>
          <option value="window">Ventana</option>
        </select>
        <input className="input" style={{ width: 100 }} type="number" min={0.2} step={0.1} value={form.rate_rps} onChange={e => setForm({ ...form, rate_rps: Number(e.target.value) })} />
        <input className="input" style={{ width: 100 }} type="number" min={1} step={1} value={form.retries} onChange={e => setForm({ ...form, retries: Number(e.target.value) })} />
        <button className="btn-dark btn-lg" onClick={save}>Guardar</button>
        <select className="select" value={scope} onChange={(e) => setScope(e.target.value as any)}>
          <option value="stock">Con stock</option>
          <option value="all">Toda la base</option>
        </select>
        <button className="btn" onClick={async () => { const ok = await ensurePlaywright(); if (!ok) return; await http.post('/admin/image-jobs/trigger/crawl-missing', null, { params: { scope } }); alert('Crawl encolado') }}>Forzar escaneo catÃ¡logo</button>
        <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/trigger/purge'); alert('Purge encolado') }}>Purgar soft-deleted</button>
  <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/clean-logs'); alert('Logs limpiados'); refresh() }}>Limpiar logs</button>
        <button className="btn" onClick={async () => {
          const title = window.prompt('TÃ­tulo a probar (proveedor Santa Planta):')
          if (!title) return
          const r = await http.post('/admin/image-jobs/probe', null, { params: { title } })
          setProbe(r.data)
        }}>Probar por tÃ­tulo</button>
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Estado</h3>
        {status ? (
          <div className="card" style={{ padding: 10 }}>
            <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
              <div><b>Activo:</b> {String(status.active)}</div>
              <div><b>Modo:</b> {status.mode}</div>
              <div><b>Running:</b> {String(status.running)}</div>
              <div><b>Pendientes:</b> {status.pending}</div>
              <div><b>OK (24h):</b> {status.ok ?? 0}</div>
              <div><b>Fail (24h):</b> {status.fail ?? 0}</div>
              {status.current_product && (
                <div>
                  <b>Procesando:</b> {status.current_product.title || ''} (ID {status.current_product.product_id}) â€” {status.current_product.stage}
                </div>
              )}
            </div>
          </div>
        ) : <div className="code">Cargando estadoâ€¦</div>}
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Logs (Ãºltimos 50)</h3>
        <div style={{ marginTop: 8 }}>
          <input className="input" placeholder="Correlation ID (opcional)" value={correlationId || ''} onChange={e => setCorrelationId(e.target.value)} style={{ width: 360, marginRight: 6 }} />
          <button className="btn" onClick={async () => { if (correlationId) await fetchSnapshots(correlationId) }}>Ver snapshots</button>
        </div>
        <div className="code" style={{ whiteSpace: 'pre-wrap', maxHeight: 320, overflow: 'auto' }}>
          {logs.map((l, i) => (<div key={i}>{l}</div>))}
        </div>
      </div>
      {snapshots.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h3>Snapshots</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {snapshots.map(s => (
              <div key={s.name} style={{ width: 180 }}>
                <div style={{ fontSize: 12 }}>{s.name}</div>
                <div style={{ marginTop: 6 }}>
                  {s.name.endsWith('.html') ? (
                    <button className="btn" onClick={() => setSelectedSnapshot(s.name)}>Ver HTML</button>
                  ) : (
                    <img src={`/admin/image-jobs/snapshots/file?path=${encodeURIComponent((correlationId || '') + '/' + s.name)}`} style={{ width: 160, height: 120, objectFit: 'cover', borderRadius: 6 }} alt={s.name} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {selectedSnapshot && (
        <div style={{ marginTop: 12 }}>
          <h3>Preview: {selectedSnapshot}</h3>
          <iframe src={`/admin/image-jobs/snapshots/file?path=${encodeURIComponent((correlationId || '') + '/' + selectedSnapshot)}`} style={{ width: '100%', height: 600, border: '1px solid #ddd' }} />
        </div>
      )}
      {probe && (
        <div style={{ marginTop: 12 }}>
          <h3>Resultado de prueba</h3>
          <div className="code" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(probe, null, 2)}</div>
          {probe.image && (<img src={probe.image} alt="preview" style={{ width: 240, height: 240, objectFit: 'cover', borderRadius: 8, marginTop: 8 }} />)}
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <h3>Pendientes de revisiÃ³n</h3>
        {pendingReview.length === 0 ? (
          <div>No hay pendientes.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table w-full">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Preview</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {pendingReview.map((r) => (
                  <tr key={r.image_id}>
                    <td>#{r.product_id}</td>
                    <td>{r.path ? <img src={`/media/${r.path}`} style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6 }} /> : '-'}</td>
                    <td>
                      <button className="btn-secondary" onClick={async () => { await http.post(`/products/images/${r.image_id}/review/approve`); refresh() }}>Aprobar</button>
                      <button className="btn" style={{ marginLeft: 6 }} onClick={async () => { await http.post(`/products/images/${r.image_id}/review/reject`, { note: 'no coincide' }); refresh() }}>Rechazar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
