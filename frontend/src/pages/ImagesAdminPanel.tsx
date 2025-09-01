// NG-HEADER: Nombre de archivo: ImagesAdminPanel.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ImagesAdminPanel.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import http from '../services/http'
import { Link } from 'react-router-dom'

export default function ImagesAdminPanel() {
  const [status, setStatus] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [form, setForm] = useState<any>({ active: false, mode: 'off', retries: 3, rate_rps: 1, burst: 3, log_retention_days: 90, purge_ttl_days: 30 })
  const [scope, setScope] = useState<'stock' | 'all'>('stock')

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function refresh() {
    try {
      const r = await http.get('/admin/image-jobs/status')
      setStatus(r.data)
      setForm((prev: any) => ({ ...prev, active: r.data.active, mode: r.data.mode }))
    const lg = await http.get('/admin/image-jobs/logs', { params: { limit: 50 } })
    const items = Array.isArray(lg.data) ? lg.data : (lg.data.items || [])
    setLogs(items)
    } catch {}
  }

  async function save() {
    await http.put('/admin/image-jobs/settings', form)
    await refresh()
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Imágenes productos</h2>
        <Link to="/admin" className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
      </div>
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
        <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/trigger/crawl-missing', null, { params: { scope } }); alert('Crawl encolado') }}>Forzar escaneo catálogo</button>
        <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/trigger/purge'); alert('Purge encolado') }}>Purgar soft-deleted</button>
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Estado</h3>
        <pre className="code" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(status, null, 2)}</pre>
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Logs (últimos 50)</h3>
        <div className="code" style={{ whiteSpace: 'pre-wrap', maxHeight: 320, overflow: 'auto' }}>
          {logs.map((l, i) => (<div key={i}>{l}</div>))}
        </div>
      </div>
    </div>
  )
}
