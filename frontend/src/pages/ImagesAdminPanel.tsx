// NG-HEADER: Nombre de archivo: ImagesAdminPanel.tsx
// NG-HEADER: Ubicación: frontend/src/pages/ImagesAdminPanel.tsx
// NG-HEADER: Descripción: Panel de imágenes con tabs para Crawler y Procesado.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState, useRef } from 'react'
import http from '../services/http'
import { Link, useNavigate } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import { serviceStatus, startService, tailServiceLogs, ServiceLogItem } from '../services/servicesAdmin'

type TabType = 'crawler' | 'procesado'

export default function ImagesAdminPanel({ embedded = false }: { embedded?: boolean }) {
  const navigate = useNavigate()

  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('crawler')

  // Crawler state
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
  const [live, setLive] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const [lastId, setLastId] = useState(0)

  // Procesado state
  const [products, setProducts] = useState<any[]>([])
  const [productsTotal, setProductsTotal] = useState(0)
  const [productsPage, setProductsPage] = useState(1)
  const [productsSearch, setProductsSearch] = useState('')
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set())
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [processingBatch, setProcessingBatch] = useState(false)
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; action: string } | null>(null)

  useEffect(() => {
    refresh()
    const id = setInterval(() => { if (!live) refresh(false) }, 6000)
    return () => { clearInterval(id); if (esRef.current) { esRef.current.close(); esRef.current = null } }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function refresh(showErrors: boolean = true) {
    try {
      const r = await http.get('/admin/image-jobs/status')
      setStatus(r.data)
      setForm((prev: any) => ({ ...prev, active: r.data.active, mode: r.data.mode }))
      // Simplify: rely on SSE when live; if not live fetch textual tail
      if (!live) {
        const lg = await http.get('/admin/image-jobs/logs', { params: { limit: 50 } })
        const items = Array.isArray(lg.data) ? lg.data : (lg.data.items || [])
        setLogs(items)
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
        try { setGatePlayLogs(await tailServiceLogs('playwright', 80)) } catch { }
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
      try { setGatePlayLogs(await tailServiceLogs('playwright', 120)) } catch { }
    } finally {
      setGatePlayBusy(false)
    }
  }

  function toggleLive() {
    const on = !live
    setLive(on)
    if (on) {
      try { if (esRef.current) { esRef.current.close(); esRef.current = null } } catch { }
      const url = new URL('/admin/image-jobs/logs/stream', window.location.origin)
      if (lastId) url.searchParams.set('last_id', String(lastId))
      const es = new EventSource(url.toString())
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data)
          if (data.logs && data.logs.length) {
            setLogs(prev => [...prev, ...data.logs.map((l: any) => `[${l.level}] ${l.created_at} - ${l.message}`)].slice(-400))
            setLastId(data.last_id || lastId)
          }
          if (data.progress && status) {
            setStatus((prev: any) => ({ ...(prev || {}), progress: data.progress }))
          }
        } catch { }
      }
      es.onerror = () => { /* ignore */ }
      esRef.current = es
    } else {
      try { if (esRef.current) esRef.current.close() } catch { }
      esRef.current = null
    }
  }

  return (
    <div className="panel p-4" style={{ margin: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Imágenes de Productos</h2>
        {!embedded && (
          <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
        )}
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: 0, marginTop: 16, marginBottom: 16, borderBottom: '2px solid var(--border, #333)' }}>
        <button
          className={activeTab === 'crawler' ? 'btn-primary' : 'btn'}
          style={{
            borderRadius: '8px 8px 0 0',
            borderBottom: activeTab === 'crawler' ? '2px solid var(--accent, #22c55e)' : 'none',
            marginBottom: -2,
            fontWeight: activeTab === 'crawler' ? 600 : 400
          }}
          onClick={() => setActiveTab('crawler')}
        >
          🔍 Crawler
        </button>
        <button
          className={activeTab === 'procesado' ? 'btn-primary' : 'btn'}
          style={{
            borderRadius: '8px 8px 0 0',
            borderBottom: activeTab === 'procesado' ? '2px solid var(--accent, #22c55e)' : 'none',
            marginBottom: -2,
            fontWeight: activeTab === 'procesado' ? 600 : 400
          }}
          onClick={() => setActiveTab('procesado')}
        >
          🖼️ Procesado
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'crawler' && (
        <div>
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
                  <button className="btn" onClick={async () => { try { setGatePlayLogs(await tailServiceLogs('playwright', 120)) } catch { } }}>Actualizar logs</button>
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
            <button className="btn" onClick={async () => { const ok = await ensurePlaywright(); if (!ok) return; await http.post('/admin/image-jobs/trigger/crawl-missing', null, { params: { scope } }); alert('Crawl encolado') }}>Forzar escaneo catálogo</button>
            <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/trigger/purge'); alert('Purge encolado') }}>Purgar soft-deleted</button>
            <button className="btn" onClick={async () => { await http.post('/admin/image-jobs/clean-logs'); alert('Logs limpiados'); refresh() }}>Limpiar logs</button>
            <button className="btn" onClick={async () => {
              const title = window.prompt('Título a probar (proveedor Santa Planta):')
              if (!title) return
              const r = await http.post('/admin/image-jobs/probe', null, { params: { title } })
              setProbe(r.data)
            }}>Probar por título</button>
            <label style={{ marginLeft: 8 }}><input type="checkbox" checked={live} onChange={toggleLive} /> Live</label>
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
                  {status.progress && (
                    <div style={{ minWidth: 220 }}>
                      <b>Progreso:</b> {status.progress.percent}% ({status.progress.processed}/{status.progress.total || '∼'})
                      <div style={{ height: 6, background: '#1f2937', borderRadius: 4, marginTop: 4 }}>
                        <div style={{ width: `${status.progress.percent}%`, height: '100%', background: '#22c55e', borderRadius: 4, transition: 'width .6s' }} />
                      </div>
                    </div>
                  )}
                  {status.current_product && (
                    <div>
                      <b>Procesando:</b> {status.current_product.title || ''} (ID {status.current_product.product_id}) — {status.current_product.stage}
                    </div>
                  )}
                </div>
              </div>
            ) : <div className="code">Cargando estado…</div>}
          </div>
          <div style={{ marginTop: 12 }}>
            <h3>Logs (últimos 50)</h3>
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
            <h3>Pendientes de revisión</h3>
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
                        <td>{r.url ? <img src={r.url} style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6 }} /> : '-'}</td>
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
      )}

      {/* Procesado Tab */}
      {activeTab === 'procesado' && (
        <div>
          {/* Search and Actions Bar */}
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div className="row" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <input
                className="input"
                placeholder="Buscar por nombre, SKU o descripción..."
                value={productsSearch}
                onChange={(e) => setProductsSearch(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') loadProducts() }}
                style={{ flex: 1, minWidth: 200 }}
              />
              <button className="btn" onClick={() => loadProducts()} disabled={loadingProducts}>
                {loadingProducts ? 'Buscando...' : '🔍 Buscar'}
              </button>
              <div style={{ borderLeft: '1px solid var(--border, #333)', height: 32, margin: '0 8px' }} />
              <span className="text-sm" style={{ opacity: 0.7 }}>
                {selectedProducts.size} seleccionados
              </span>
              <button
                className="btn-primary"
                disabled={selectedProducts.size === 0 || processingBatch}
                onClick={handleBatchWebP}
              >
                🖼️ Generar WebP
              </button>
              <button
                className="btn"
                disabled={selectedProducts.size === 0 || processingBatch}
                onClick={handleBatchWatermark}
              >
                💧 Watermark
              </button>
            </div>
            {batchProgress && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 14, marginBottom: 4 }}>
                  {batchProgress.action}: {batchProgress.current}/{batchProgress.total}
                </div>
                <div style={{ height: 6, background: '#1f2937', borderRadius: 4 }}>
                  <div style={{
                    width: `${(batchProgress.current / batchProgress.total) * 100}%`,
                    height: '100%',
                    background: '#22c55e',
                    borderRadius: 4,
                    transition: 'width .3s'
                  }} />
                </div>
              </div>
            )}
          </div>

          {/* Products Table */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="table w-full">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        checked={products.length > 0 && selectedProducts.size === products.length}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedProducts(new Set(products.map(p => p.product_id)))
                          } else {
                            setSelectedProducts(new Set())
                          }
                        }}
                      />
                    </th>
                    <th style={{ width: 80 }}>Imagen</th>
                    <th>Producto</th>
                    <th style={{ width: 140 }}>SKU</th>
                    <th style={{ width: 100 }}>Tags</th>
                    <th style={{ width: 80 }}>Imágenes</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingProducts ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32 }}>Cargando productos...</td></tr>
                  ) : products.length === 0 ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, opacity: 0.6 }}>
                      {productsSearch ? 'No se encontraron productos' : 'Ingresá una búsqueda para ver productos'}
                    </td></tr>
                  ) : (
                    products.map((p) => (
                      <tr key={p.product_id} style={{ background: selectedProducts.has(p.product_id) ? 'rgba(34, 197, 94, 0.1)' : undefined }}>
                        <td onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedProducts.has(p.product_id)}
                            onChange={(e) => {
                              const next = new Set(selectedProducts)
                              if (e.target.checked) {
                                next.add(p.product_id)
                              } else {
                                next.delete(p.product_id)
                              }
                              setSelectedProducts(next)
                            }}
                          />
                        </td>
                        <td
                          style={{ cursor: 'pointer' }}
                          onClick={() => navigate(PATHS.productImages(p.product_id))}
                        >
                          {p.image_url ? (
                            <img
                              src={p.image_url}
                              style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 6 }}
                              alt={p.title}
                            />
                          ) : (
                            <div style={{
                              width: 60, height: 60,
                              background: 'var(--bg-secondary, #1a1a1a)',
                              borderRadius: 6,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 24,
                              opacity: 0.3
                            }}>📷</div>
                          )}
                        </td>
                        <td
                          style={{ cursor: 'pointer' }}
                          onClick={() => navigate(PATHS.productImages(p.product_id))}
                        >
                          <div style={{ fontWeight: 500 }}>{p.preferred_name || p.name}</div>
                          <div className="text-sm" style={{ opacity: 0.6, marginTop: 2 }}>
                            ID: {p.product_id}
                          </div>
                        </td>
                        <td>
                          {p.canonical_sku ? (
                            <span style={{
                              background: 'var(--accent, #22c55e)',
                              color: '#000',
                              padding: '2px 6px',
                              borderRadius: 4,
                              fontSize: 12,
                              fontWeight: 600
                            }}>
                              {p.canonical_sku}
                            </span>
                          ) : p.sku_root || '-'}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {(p.tags || []).slice(0, 3).map((t: any) => (
                              <span key={t.id} style={{
                                background: 'var(--bg-secondary, #1a1a1a)',
                                padding: '2px 6px',
                                borderRadius: 4,
                                fontSize: 11
                              }}>
                                {t.name}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td
                          style={{ textAlign: 'center', cursor: 'pointer' }}
                          onClick={() => navigate(PATHS.productImages(p.product_id))}
                        >
                          {p.images_count || 0}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            {productsTotal > 20 && (
              <div className="row" style={{ justifyContent: 'center', gap: 8, marginTop: 16 }}>
                <button
                  className="btn"
                  disabled={productsPage <= 1}
                  onClick={() => { setProductsPage(p => p - 1); loadProducts(productsPage - 1) }}
                >
                  ← Anterior
                </button>
                <span style={{ padding: '8px 16px' }}>
                  Página {productsPage} de {Math.ceil(productsTotal / 20)}
                </span>
                <button
                  className="btn"
                  disabled={productsPage >= Math.ceil(productsTotal / 20)}
                  onClick={() => { setProductsPage(p => p + 1); loadProducts(productsPage + 1) }}
                >
                  Siguiente →
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )

  // Procesado functions
  async function loadProducts(page = productsPage) {
    setLoadingProducts(true)
    try {
      const params: any = { page, page_size: 20 }
      if (productsSearch.trim()) {
        params.q = productsSearch.trim()
      }
      const r = await http.get('/products', { params })
      setProducts(r.data.items || [])
      setProductsTotal(r.data.total || 0)
    } catch (e) {
      console.warn('loadProducts error', e)
    } finally {
      setLoadingProducts(false)
    }
  }

  async function handleBatchWebP() {
    if (selectedProducts.size === 0) return
    setProcessingBatch(true)
    const ids = Array.from(selectedProducts)
    setBatchProgress({ current: 0, total: ids.length, action: 'Generando WebP' })

    let successCount = 0
    for (let i = 0; i < ids.length; i++) {
      const productId = ids[i]
      setBatchProgress({ current: i + 1, total: ids.length, action: 'Generando WebP' })
      try {
        // Get product images
        const prod = products.find(p => p.product_id === productId)
        if (prod && prod.primary_image_id) {
          await http.post(`/products/${productId}/images/${prod.primary_image_id}/generate-webp`)
          successCount++
        }
      } catch (e) {
        console.warn('WebP generation error for product', productId, e)
      }
    }

    setBatchProgress(null)
    setProcessingBatch(false)
    alert(`WebP generado para ${successCount}/${ids.length} productos`)
    loadProducts()
  }

  async function handleBatchWatermark() {
    if (selectedProducts.size === 0) return
    setProcessingBatch(true)
    const ids = Array.from(selectedProducts)
    setBatchProgress({ current: 0, total: ids.length, action: 'Aplicando Watermark' })

    let successCount = 0
    for (let i = 0; i < ids.length; i++) {
      const productId = ids[i]
      setBatchProgress({ current: i + 1, total: ids.length, action: 'Aplicando Watermark' })
      try {
        const prod = products.find(p => p.product_id === productId)
        if (prod && prod.primary_image_id) {
          await http.post(`/products/${productId}/images/${prod.primary_image_id}/process/watermark`, {})
          successCount++
        }
      } catch (e) {
        console.warn('Watermark error for product', productId, e)
      }
    }

    setBatchProgress(null)
    setProcessingBatch(false)
    alert(`Watermark aplicado a ${successCount}/${ids.length} productos`)
    loadProducts()
  }
}
